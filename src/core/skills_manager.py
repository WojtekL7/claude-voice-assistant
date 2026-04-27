"""
Skills Manager - lokalne zarządzanie skillami Claude Code.

Operuje na katalogu ~/.claude/skills/<name>/, gdzie każdy skill to folder
zawierający plik SKILL.md (z opcjonalnym frontmatterem name/description)
oraz dodatkowe pliki (skrypty, szablony, instrukcje).

Claude Code natywnie odczytuje ten katalog i automatycznie aktywuje skill
gdy jego opis pasuje do treści rozmowy.
"""
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


SKILLS_DIR = Path.home() / ".claude" / "skills"


class SkillInstallError(Exception):
    """Raised when a skill cannot be installed (missing SKILL.md, conflict, etc.)."""


@dataclass
class Skill:
    name: str
    description: str
    folder_path: Path
    has_metadata: bool  # True jeśli SKILL.md istnieje i miał frontmatter

    @property
    def folder_name(self) -> str:
        return self.folder_path.name


class SkillsManager:
    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or SKILLS_DIR

    def ensure_dir(self) -> None:
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def list_skills(self) -> List[Skill]:
        if not self.skills_dir.exists():
            return []

        skills: List[Skill] = []
        for entry in sorted(self.skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if skill_md.exists():
                try:
                    meta = self._parse_frontmatter(skill_md.read_text(encoding="utf-8"))
                except OSError:
                    meta = {}
                skills.append(Skill(
                    name=meta.get("name") or entry.name,
                    description=meta.get("description") or "",
                    folder_path=entry,
                    has_metadata=bool(meta),
                ))
            else:
                skills.append(Skill(
                    name=entry.name,
                    description="(brak pliku SKILL.md)",
                    folder_path=entry,
                    has_metadata=False,
                ))
        return skills

    def install_from_folder(self, src_folder: Path, *, overwrite: bool = False) -> Skill:
        src_folder = Path(src_folder)
        if not src_folder.is_dir():
            raise SkillInstallError(f"Nie znaleziono folderu: {src_folder}")

        # SKILL.md może być w korzeniu folderu lub o jeden poziom niżej.
        skill_root = self._find_skill_root(src_folder)
        if skill_root is None:
            raise SkillInstallError(
                "W tym folderze nie znaleziono pliku SKILL.md. "
                "Skill musi mieć SKILL.md w katalogu głównym."
            )

        return self._copy_skill_root(skill_root, overwrite=overwrite)

    def install_from_zip(self, zip_path: Path, *, overwrite: bool = False) -> Skill:
        zip_path = Path(zip_path)
        if not zip_path.is_file():
            raise SkillInstallError(f"Nie znaleziono pliku: {zip_path}")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            try:
                with zipfile.ZipFile(zip_path) as zf:
                    self._safe_extract_zip(zf, tmp_path)
            except zipfile.BadZipFile as exc:
                raise SkillInstallError(f"Nieprawidłowy plik ZIP: {exc}")

            skill_root = self._find_skill_root(tmp_path)
            if skill_root is None:
                raise SkillInstallError(
                    "W tym ZIP nie znaleziono pliku SKILL.md. "
                    "Sprawdź czy archiwum zawiera prawidłowy skill."
                )

            return self._copy_skill_root(skill_root, overwrite=overwrite)

    def remove(self, folder_name: str) -> bool:
        target = self.skills_dir / folder_name
        if not target.exists() or not target.is_dir():
            return False
        # Sanity check — nie pozwól wyjść poza skills_dir.
        if self.skills_dir not in target.resolve().parents:
            raise SkillInstallError("Próba usunięcia poza katalogiem skilli — operacja przerwana.")
        shutil.rmtree(target)
        return True

    # ---------- Helpers ----------

    def _copy_skill_root(self, skill_root: Path, *, overwrite: bool) -> Skill:
        self.ensure_dir()
        target = self.skills_dir / skill_root.name

        if target.exists():
            if not overwrite:
                raise SkillInstallError(
                    f"Skill '{skill_root.name}' już istnieje. "
                    "Usuń go najpierw lub użyj nadpisania."
                )
            shutil.rmtree(target)

        shutil.copytree(skill_root, target)

        skill_md = target / "SKILL.md"
        meta = {}
        if skill_md.exists():
            try:
                meta = self._parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            except OSError:
                meta = {}

        return Skill(
            name=meta.get("name") or target.name,
            description=meta.get("description") or "",
            folder_path=target,
            has_metadata=bool(meta),
        )

    @staticmethod
    def _find_skill_root(base: Path) -> Optional[Path]:
        """Szuka folderu zawierającego SKILL.md — w base albo o jeden poziom głębiej."""
        if (base / "SKILL.md").exists():
            return base
        for sub in base.iterdir():
            if sub.is_dir() and (sub / "SKILL.md").exists():
                return sub
        return None

    @staticmethod
    def _safe_extract_zip(zf: zipfile.ZipFile, dest: Path) -> None:
        """Wypakowuje ZIP odrzucając wpisy spoza dest (zip-slip)."""
        dest_resolved = dest.resolve()
        for member in zf.namelist():
            target = (dest / member).resolve()
            if dest_resolved not in target.parents and target != dest_resolved:
                raise SkillInstallError(
                    f"ZIP zawiera niebezpieczną ścieżkę '{member}'. Instalacja przerwana."
                )
        zf.extractall(dest)

    @staticmethod
    def _parse_frontmatter(content: str) -> dict:
        """Bardzo prosty parser YAML frontmattera (klucz: wartość, jedna linia).

        Frontmatter zaczyna się od '---' w pierwszej linii i kończy '---'
        w kolejnej linii. Nie obsługuje list, zagnieżdżeń ani multi-line —
        wystarczy do pól `name` i `description`.
        """
        if not content.startswith("---"):
            return {}
        end_marker = content.find("\n---", 3)
        if end_marker < 0:
            return {}
        body = content[3:end_marker].strip()

        result: dict = {}
        for raw_line in body.split("\n"):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"').strip("'")
        return result

"""
Claude Voice Assistant - Text Cleaner for TTS
Cleans terminal output for natural speech synthesis.
"""
import re
from typing import Optional, List


def fix_polish_encoding(text: str) -> str:
    """
    Fix common UTF-8/Latin-1 encoding issues with Polish characters.

    When QTermWidget outputs UTF-8 text, the continuation bytes (0x80-0xBF)
    are sometimes lost, leaving orphaned lead bytes (Ã, Ä, Å).

    This function:
    1. Fixes complete 2-byte sequences (Ã³ -> ó)
    2. Removes orphaned lead bytes so TTS doesn't read garbage
    """
    if not text:
        return text

    # Method 1: Try full Latin-1 -> UTF-8 conversion
    # ONLY use if it produces MORE characters than input (no data loss)
    # This method is lossy when UTF-8 bytes are partially corrupted
    method1_result = None
    try:
        fixed = text.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
        # Only use if we didn't lose too many characters (max 10% loss allowed)
        if len(fixed) >= len(text) * 0.9:
            if any(c in fixed for c in 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ'):
                method1_result = fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    # Method 2: Fix complete 2-char sequences that survived intact
    # Format: 'broken_sequence': 'correct_char'
    # These are UTF-8 bytes (c3 XX or c4 XX or c5 XX) interpreted as Latin-1
    complete_sequences = {
        # Ã + second byte (C3 XX) - accented vowels
        'Ã³': 'ó', 'Ã"': 'Ó',  # ó/Ó
        'Ã¡': 'á', 'Ã': 'Á',  # á/Á
        'Ã©': 'é', 'Ã‰': 'É',  # é/É
        'Ã­': 'í', 'Ã': 'Í',  # í/Í
        'Ãº': 'ú', 'Ãš': 'Ú',  # ú/Ú
        'Ã±': 'ñ', 'Ã\x91': 'Ñ',  # ñ/Ñ
        # Ä + second byte (C4 XX) - Polish ąćę
        'Ä…': 'ą', 'Ä„': 'Ą',  # ą/Ą
        'Ä‡': 'ć', 'Ä†': 'Ć',  # ć/Ć
        'Ä™': 'ę', 'Ä˜': 'Ę',  # ę/Ę
        # Å + second byte (C5 XX) - Polish łńśźż
        'Å‚': 'ł', 'Å\x81': 'Ł',  # ł/Ł (note: Ł is C5 81)
        'Å„': 'ń', 'Åƒ': 'Ń',  # ń/Ń
        'Å›': 'ś', 'Åš': 'Ś',  # ś/Ś
        'Åº': 'ź', 'Å¹': 'Ź',  # ź/Ź
        'Å¼': 'ż', 'Å»': 'Ż',  # ż/Ż
    }

    result = text
    for broken, fixed_char in complete_sequences.items():
        result = result.replace(broken, fixed_char)

    # Method 3: Try to recover common Polish patterns from corrupted UTF-8
    # When QTermWidget loses continuation bytes, we can sometimes guess the character
    # based on context (what letter follows the orphaned lead byte)

    # Common patterns: Å + letter often indicates ł, ś, ń, ź, ż
    # Ä + letter often indicates ą, ć, ę
    polish_recovery = [
        # PRIORITY: Specific word patterns FIRST (before general patterns)
        # Common words ending in ę: się, mię, cię, ję
        (r'siÄ\b', 'się'), (r'siÄ$', 'się'),
        (r'miÄ\b', 'mię'), (r'miÄ$', 'mię'),
        (r'ciÄ\b', 'cię'), (r'ciÄ$', 'cię'),
        (r'jÄ\b', 'ję'), (r'jÄ$', 'ję'),

        # Å patterns (C5 XX) - ł is most common, then ś, ń, ż
        (r'Åa', 'ła'), (r'Åo', 'ło'), (r'Åu', 'łu'), (r'Åe', 'łe'), (r'Åi', 'łi'), (r'Åy', 'ły'),
        (r'ÅA', 'ŁA'), (r'ÅO', 'ŁO'), (r'ÅU', 'ŁU'), (r'ÅE', 'ŁE'), (r'ÅI', 'ŁI'), (r'ÅY', 'ŁY'),
        (r'Åw', 'św'), (r'Åm', 'śm'), (r'Ål', 'śl'), (r'Åp', 'śp'), (r'Åc', 'śc'), (r'År', 'śr'),
        (r'Ån', 'śn'),  # ślub, świat, śmiech, etc.
        # ÅN, ÅZ patterns - likely Ż (WAŻNE, RÓŻNE)
        (r'ÅN', 'ŻN'), (r'ÅZ', 'ŻZ'), (r'ÅB', 'ŻB'), (r'ÅD', 'ŻD'),

        # Ä patterns (C4 XX) - context-dependent
        # Verb endings: -ać, -ić, -yć, -eć, -uć → ć
        (r'aÄ\b', 'ać'), (r'aÄ$', 'ać'),
        (r'iÄ\b', 'ić'), (r'iÄ$', 'ić'),
        (r'yÄ\b', 'yć'), (r'yÄ$', 'yć'),
        (r'eÄ\b', 'eć'), (r'eÄ$', 'eć'),
        (r'uÄ\b', 'uć'), (r'uÄ$', 'uć'),
        (r'oÄ\b', 'oć'), (r'oÄ$', 'oć'),  # Added: -oć endings
        (r'AÄ\b', 'AĆ'), (r'IÄ\b', 'IĆ'), (r'YÄ\b', 'YĆ'), (r'EÄ\b', 'EĆ'), (r'UÄ\b', 'UĆ'),

        # Ä followed by consonants → ę (kliknięcia, więcej, etc.)
        (r'Äc', 'ęc'), (r'Äk', 'ęk'), (r'Ät', 'ęt'), (r'Äd', 'ęd'), (r'Äb', 'ęb'),
        (r'Äp', 'ęp'), (r'Äs', 'ęs'), (r'Äz', 'ęz'), (r'Är', 'ęr'), (r'Äl', 'ęl'),
        (r'Äj', 'ęj'),  # więcej

        # Remaining Ä with punctuation → ę
        (r'Ä\s', 'ę '), (r'Ä\.', 'ę.'), (r'Ä,', 'ę,'), (r'Ä\?', 'ę?'), (r'Ä!', 'ę!'),

        # Ã patterns (C3 XX) - ó is most common
        (r'Ão', 'ó'), (r'Ãó', 'ó'),
    ]

    for pattern, replacement in polish_recovery:
        result = re.sub(pattern, replacement, result)

    # Remove any remaining orphaned lead bytes
    result = re.sub(r'[ÄÅÃ](?=[a-zA-Z0-9])', '', result)
    result = re.sub(r'[ÄÅÃ]$', '', result)

    # Compare Method 1 vs Method 2+3 results - use the one with more Polish chars
    if method1_result:
        polish_chars = 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ'
        method1_polish = sum(1 for c in method1_result if c in polish_chars)
        method23_polish = sum(1 for c in result if c in polish_chars)
        # Use method 2+3 if it has more Polish chars OR similar with more total chars
        if method23_polish > method1_polish:
            return result
        elif method23_polish == method1_polish and len(result) > len(method1_result):
            return result
        else:
            return method1_result

    return result

# Try to import PyEnchant for dictionary filtering
try:
    import enchant
    ENCHANT_AVAILABLE = True
except ImportError:
    ENCHANT_AVAILABLE = False


class TextCleanerForTTS:
    """
    Cleans text from terminal output for Text-to-Speech.
    Removes URLs, special characters, code blocks, and non-dictionary words.
    """

    def __init__(self, language: str = "pl_PL"):
        self.language = language
        self._dict = None
        self._init_dictionary()

        # Compile regex patterns for performance
        self._patterns = {
            # ANSI escape codes (colors, formatting)
            'ansi': re.compile(r'(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]'),
            # OSC sequences (terminal title, etc.)
            'osc': re.compile(r'\x1B\][^\x07]*\x07'),
            # URLs (http, https, ftp)
            'urls': re.compile(r'https?://\S+|ftp://\S+|www\.\S+'),
            # File paths (Unix style)
            'paths': re.compile(r'(?<!\w)[/~][\w./-]+(?:\.\w+)?'),
            # Email addresses
            'emails': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            # Code blocks (markdown)
            'code_blocks': re.compile(r'```[\s\S]*?```', re.MULTILINE),
            # Inline code (markdown)
            'inline_code': re.compile(r'`[^`]+`'),
            # Multiple dashes, equals, underscores (separators)
            'separators': re.compile(r'[-=_#]{3,}'),
            # Multiple dots
            'dots': re.compile(r'\.{3,}'),
            # Multiple spaces/newlines
            'whitespace': re.compile(r'\s+'),
            # Special characters sequences (arrows, boxes, etc.)
            'special_chars': re.compile(r'[│├└┐┌┘┬┴┼─═║╔╗╚╝╠╣╬▶▷◀◁●○■□★☆→←↑↓⬆⬇\*]+'),
            # Emoji and special Unicode symbols
            'emoji': re.compile(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF]+'),
            # Git hashes (7+ hex characters)
            'git_hash': re.compile(r'\b[a-f0-9]{7,40}\b'),
            # Version numbers like v2.0.76
            'versions': re.compile(r'\bv?\d+\.\d+\.\d+[a-z0-9.-]*\b'),
            # Technical tokens (camelCase, snake_case identifiers)
            'identifiers': re.compile(r'\b[a-z]+(?:[A-Z][a-z]+)+\b|\b[a-z]+(?:_[a-z]+){2,}\b'),
            # Command prompts and shell stuff
            'prompts': re.compile(r'^[\$#>%]\s*', re.MULTILINE),
            # Line numbers (like "123:")
            'line_numbers': re.compile(r'^\s*\d+[:\|]\s*', re.MULTILINE),
            # Brew/npm/pip install output patterns
            'package_managers': re.compile(r'(==>|-->|\*\*\*|Installing|Downloading|Pouring|Fetching|Building)\s+.*', re.IGNORECASE),
            # Progress indicators
            'progress': re.compile(r'[\[\(]?\d+[%/]\d*[\]\)]?|\.{2,}|#{2,}'),
            # Command line flags
            'cli_flags': re.compile(r'\s--?\w+[-\w]*'),
        }

        # Words to always filter out (technical jargon)
        self._filter_words = {
            'npm', 'git', 'pip', 'sudo', 'chmod', 'mkdir', 'cd', 'ls', 'rm',
            'docker', 'kubectl', 'ssh', 'scp', 'curl', 'wget', 'grep', 'sed',
            'awk', 'cat', 'echo', 'export', 'env', 'bash', 'zsh', 'sh',
            'stdout', 'stderr', 'stdin', 'args', 'kwargs', 'params',
            'api', 'url', 'uri', 'http', 'https', 'ftp', 'tcp', 'udp',
            'json', 'xml', 'html', 'css', 'js', 'ts', 'py', 'rb', 'go',
            'async', 'await', 'const', 'let', 'var', 'def', 'func', 'fn',
            'int', 'str', 'bool', 'float', 'dict', 'list', 'tuple', 'set',
            'null', 'none', 'nil', 'undefined', 'true', 'false',
            'ok', 'err', 'error', 'warning', 'info', 'debug', 'trace',
            'todo', 'fixme', 'hack', 'xxx', 'note', 'cmake', 'make',
            'brew', 'homebrew', 'apt', 'yum', 'pacman', 'dpkg',
            'node', 'deno', 'bun', 'yarn', 'pnpm', 'cargo', 'rustc',
            'gcc', 'clang', 'llvm', 'ninja', 'swig', 'pcre', 'zlib',
        }

    def _init_dictionary(self):
        """Initialize spell-checking dictionary."""
        if not ENCHANT_AVAILABLE:
            return

        # Map language codes
        lang_map = {
            'pl-PL': 'pl_PL', 'pl_PL': 'pl_PL', 'pl': 'pl_PL',
            'en-US': 'en_US', 'en_US': 'en_US', 'en': 'en_US',
            'en-GB': 'en_GB', 'en_GB': 'en_GB',
            'de-DE': 'de_DE', 'de_DE': 'de_DE', 'de': 'de_DE',
            'fr-FR': 'fr_FR', 'fr_FR': 'fr_FR', 'fr': 'fr_FR',
            'es-ES': 'es_ES', 'es_ES': 'es_ES', 'es': 'es_ES',
        }

        dict_lang = lang_map.get(self.language, 'en_US')

        try:
            if enchant.dict_exists(dict_lang):
                self._dict = enchant.Dict(dict_lang)
            elif enchant.dict_exists('en_US'):
                self._dict = enchant.Dict('en_US')
        except Exception as e:
            print(f"Warning: Could not initialize dictionary: {e}")
            self._dict = None

    def set_language(self, language: str):
        """Change the dictionary language."""
        self.language = language
        self._init_dictionary()

    def clean(self, text: str, use_dictionary: bool = True) -> str:
        """
        Clean text for TTS reading.

        Args:
            text: Raw text from terminal
            use_dictionary: Whether to filter non-dictionary words

        Returns:
            Cleaned text suitable for TTS
        """
        if not text:
            return ""

        # Step 1: Remove ANSI and OSC escape codes
        text = self._patterns['ansi'].sub('', text)
        text = self._patterns['osc'].sub('', text)

        # Step 2: Remove code blocks first (before other processing)
        text = self._patterns['code_blocks'].sub('', text)
        text = self._patterns['inline_code'].sub('', text)

        # Step 3: Remove package manager output
        text = self._patterns['package_managers'].sub('', text)

        # Step 4: Remove URLs, paths, emails
        text = self._patterns['urls'].sub('', text)
        text = self._patterns['paths'].sub('', text)
        text = self._patterns['emails'].sub('', text)

        # Step 5: Remove technical patterns
        text = self._patterns['git_hash'].sub('', text)
        text = self._patterns['versions'].sub('', text)
        text = self._patterns['line_numbers'].sub('', text)
        text = self._patterns['prompts'].sub('', text)
        text = self._patterns['cli_flags'].sub(' ', text)
        text = self._patterns['progress'].sub('', text)

        # Step 6: Remove visual elements
        text = self._patterns['separators'].sub(' ', text)
        text = self._patterns['dots'].sub('.', text)
        text = self._patterns['special_chars'].sub('', text)
        text = self._patterns['emoji'].sub('', text)

        # Step 7: Filter words
        if use_dictionary:
            text = self._filter_words_by_dictionary(text)
        else:
            text = self._filter_technical_words(text)

        # Step 8: Remove duplicate lines/sentences
        text = self._remove_duplicates(text)

        # Step 9: Normalize whitespace
        text = self._patterns['whitespace'].sub(' ', text)
        text = text.strip()

        # Step 10: Clean up punctuation
        text = self._clean_punctuation(text)

        # Step 11: Limit length (max ~500 words for TTS)
        words = text.split()
        if len(words) > 500:
            text = ' '.join(words[:500]) + '...'

        return text

    def _remove_duplicates(self, text: str) -> str:
        """Remove duplicate lines and repeated sentences."""
        lines = text.split('\n')
        seen = set()
        unique_lines = []

        for line in lines:
            # Normalize for comparison
            normalized = ' '.join(line.split()).lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_lines.append(line)

        return '\n'.join(unique_lines)

    def _filter_technical_words(self, text: str) -> str:
        """Filter out known technical words."""
        words = text.split()
        filtered = []

        for word in words:
            # Clean word for comparison
            clean_word = word.lower().strip('.,!?;:()[]{}"\'-')

            # Skip if in filter list
            if clean_word in self._filter_words:
                continue

            # Skip if looks like a technical identifier
            if self._looks_technical(clean_word):
                continue

            filtered.append(word)

        return ' '.join(filtered)

    def _filter_words_by_dictionary(self, text: str) -> str:
        """Filter words not in dictionary."""
        if not self._dict:
            return self._filter_technical_words(text)

        words = text.split()
        filtered = []

        for word in words:
            # Clean word for dictionary check
            clean_word = word.strip('.,!?;:()[]{}"\'-')

            # Skip empty
            if not clean_word:
                continue

            # Skip numbers
            if clean_word.isdigit():
                filtered.append(word)
                continue

            # Skip very short words (likely abbreviations)
            if len(clean_word) <= 2:
                filtered.append(word)
                continue

            # Skip if in filter list
            if clean_word.lower() in self._filter_words:
                continue

            # Skip if looks technical
            if self._looks_technical(clean_word):
                continue

            # Check dictionary
            try:
                if self._dict.check(clean_word) or self._dict.check(clean_word.lower()):
                    filtered.append(word)
                # Also accept capitalized versions (proper nouns)
                elif self._dict.check(clean_word.capitalize()):
                    filtered.append(word)
            except:
                # On error, include the word
                filtered.append(word)

        return ' '.join(filtered)

    def _looks_technical(self, word: str) -> bool:
        """Check if word looks like technical jargon."""
        if not word:
            return False

        # Skip check for words with corrupted Polish encoding
        # These characters appear when UTF-8 Polish text is decoded as Latin-1
        # Includes both uppercase and lowercase variants after .lower()
        corrupted_polish_chars = 'ÄÃÅĄĆĘŁŃÓŚŹŻąćęłńóśźżäãåšžřčďťňéèêëàâùûîïôœæø³¹²'
        if any(c in word for c in corrupted_polish_chars):
            return False

        # Contains underscores or special chars (but not corrupted Polish)
        if '_' in word or '@' in word or '#' in word:
            return True

        # Contains digits mixed with letters (like "v2", "test123")
        # But allow standalone numbers and version numbers
        has_digits = any(c.isdigit() for c in word)
        has_letters = any(c.isalpha() for c in word)
        if has_digits and has_letters:
            # Allow version-like patterns that start with digit
            if re.match(r'^\d+\.?\d*$', word):
                return False
            return True

        # CamelCase pattern (strict: lowercase then uppercase, ASCII only)
        if re.match(r'^[a-z]+(?:[A-Z][a-z]+)+$', word):
            return True

        # All caps and longer than 4 chars (likely acronym) - ASCII only
        if word.isupper() and len(word) > 4 and word.isascii():
            return True

        # File extension pattern
        if re.match(r'^\.\w+$', word):
            return True

        return False

    def _clean_punctuation(self, text: str) -> str:
        """Clean up punctuation for natural reading."""
        # Remove multiple punctuation
        text = re.sub(r'([.,!?;:])\1+', r'\1', text)

        # Remove punctuation at start
        text = re.sub(r'^[.,;:]+', '', text)

        # Add space after punctuation if missing
        text = re.sub(r'([.,!?;:])([A-Za-z])', r'\1 \2', text)

        # Remove orphan punctuation
        text = re.sub(r'\s+([.,!?;:])\s+', r'\1 ', text)

        return text.strip()


def extract_last_claude_response(terminal_buffer: str) -> str:
    """
    Extract the last Claude Code response from terminal buffer.

    Claude Code UI structure:
    - User prompt: "> user text" inside ASCII box frames
    - Claude response: Natural text WITHOUT frames
    - UI elements: frames (─═│╭╮), tips, shortcuts, status messages

    Args:
        terminal_buffer: Raw terminal output buffer

    Returns:
        The last Claude response text (clean, readable)
    """
    if not terminal_buffer:
        return ""

    # Step 1: Clean ANSI/OSC escape codes
    ansi_pattern = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]')
    osc_pattern = re.compile(r'\x1B\][^\x07]*\x07')
    control_pattern = re.compile(r'\[\?2026[hl]')  # Terminal control sequences

    clean_buffer = ansi_pattern.sub('', terminal_buffer)
    clean_buffer = osc_pattern.sub('', clean_buffer)
    clean_buffer = control_pattern.sub('', clean_buffer)

    # Step 2: Remove ALL ASCII box drawing characters (Claude Code UI frames)
    # This includes: ─━│┃┄┅┆┇┈┉┊┋═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬
    # And also: ╭╮╯╰┌┐└┘├┤┬┴┼
    box_chars = re.compile(r'[─━│┃┄┅┆┇┈┉┊┋═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬╭╮╯╰┌┐└┘├┤┬┴┼▶▷◀◁●○■□★☆→←↑↓⬆⬇❯]+')
    clean_buffer = box_chars.sub('', clean_buffer)

    # Step 3: Remove Claude Code UI elements (specific patterns)
    # Note: Some patterns need to match corrupted UTF-8 chars (â¢ becomes ¢, â¦ becomes ¦, · becomes Â·)
    spinner_words = r'(Vibing|Germinating|Determining|Thinking|Processing|Cerebrating|Creating|Envisioning|Reasoning|Analyzing|Considering|Pondering|Reflecting|Contemplating|Working)'
    ui_patterns = [
        # PRIORITY: Direct match for exact formats seen in debug (must be first!)
        # "Â· Creating¦ (" pattern - match the bullet, spinner word, broken pipe, space, open paren
        re.compile(r'Â·\s*' + spinner_words + r'¦\s*\(', re.IGNORECASE),
        re.compile(r'·\s*' + spinner_words + r'¦\s*\(', re.IGNORECASE),
        # Spinner words followed by ¦ (broken ellipsis)
        re.compile(spinner_words + r'¦', re.IGNORECASE),
        # Spinners with bullet/star prefixes and optional ellipsis
        re.compile(r'[·Â·\*\•\¢¦]+\s*' + spinner_words + r'[¦â¦\.]*', re.IGNORECASE),
        # Spinner with full (esc to interrupt) - use non-greedy match
        re.compile(spinner_words + r'[â¦¦\.]{0,3}\s*\([^)]{0,30}\)', re.IGNORECASE),
        # Spinner at end of line
        re.compile(spinner_words + r'[â¦¦\.]+.*$', re.MULTILINE | re.IGNORECASE),
        # Spinner with interrupt text
        re.compile(spinner_words + r'.*interrupt.*$', re.MULTILINE | re.IGNORECASE),
        # Standalone bullet + spinner
        re.compile(r'·\s*' + spinner_words + r'[¦â¦\.]*', re.IGNORECASE),
        # Tips and hints
        re.compile(r'Tip:.*$', re.MULTILINE | re.IGNORECASE),
        re.compile(r'✿\s*Tip:.*$', re.MULTILINE),
        # Keyboard shortcuts hints
        re.compile(r'\?\s*for\s*shortcuts.*$', re.MULTILINE | re.IGNORECASE),
        re.compile(r'esc\s*to\s*interrupt.*$', re.MULTILINE | re.IGNORECASE),
        re.compile(r'↵\s*send.*$', re.MULTILINE | re.IGNORECASE),
        # Status messages
        re.compile(r'Auto-update\s*failed.*$', re.MULTILINE | re.IGNORECASE),
        re.compile(r'Try\s*claude\s*doctor.*$', re.MULTILINE | re.IGNORECASE),
        re.compile(r'npm\s*i\s*-g\s*@anthropic.*$', re.MULTILINE | re.IGNORECASE),
        # Spinners and loading indicators (various Unicode and corrupted versions)
        re.compile(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏✿⋆▶▷◀◁●○â¶â»â½â¢¢\*]+\s*', re.MULTILINE),
        # Empty prompts
        re.compile(r'^>\s*$', re.MULTILINE),
        re.compile(r'^❯\s*$', re.MULTILINE),
        # User prompts (line starting with > followed by user text)
        re.compile(r'^>\s+.+$', re.MULTILINE),
        re.compile(r'^❯\s+.+$', re.MULTILINE),
    ]

    for pattern in ui_patterns:
        clean_buffer = pattern.sub('', clean_buffer)

    # Step 4: Remove technical/log output patterns
    technical_patterns = [
        # Log lines with brackets
        re.compile(r'^\s*\[[\w-]+\].*$', re.MULTILINE),
        # Email/IMAP processing logs
        re.compile(r'^\s*(Searching|Fetched|Parsed|Email|WebSocket|IMAP).*$', re.MULTILINE | re.IGNORECASE),
        re.compile(r'^\s*\d+\s*from\s+\S+@\S+.*$', re.MULTILINE),  # "2400 from email@domain"
        re.compile(r'^\s*Search results for.*$', re.MULTILINE),
        re.compile(r'^\s*\[Auto-Comment\].*$', re.MULTILINE),
        # File paths
        re.compile(r'^\s*/[\w/.-]+\s*$', re.MULTILINE),
        # URLs
        re.compile(r'https?://\S+'),
        # Package manager output
        re.compile(r'^\s*(Installing|Downloading|Pouring|Fetching|Building|Compiling).*$', re.MULTILINE | re.IGNORECASE),
        # Shell prompts
        re.compile(r'^\s*[\w-]+@[\w.-]+[:\s$#%].*$', re.MULTILINE),
        re.compile(r'^\s*\$\s*\S+.*$', re.MULTILINE),
    ]

    for pattern in technical_patterns:
        clean_buffer = pattern.sub('', clean_buffer)

    # Step 5: Split into lines and filter
    lines = clean_buffer.split('\n')

    # Find lines that look like natural language (Claude's response)
    natural_lines = []
    for line in lines:
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Skip very short lines (< 10 chars)
        if len(stripped) < 10:
            continue

        # Skip lines that are mostly non-alphabetic
        alpha_count = sum(1 for c in stripped if c.isalpha())
        if len(stripped) > 0 and alpha_count / len(stripped) < 0.5:
            continue

        # Skip lines that look like status/metadata
        if stripped.startswith(('Status:', 'Error:', 'Warning:', 'Note:', 'UID', 'seqno')):
            continue

        # This looks like natural language - keep it
        natural_lines.append(stripped)

    # Step 6: Find the LAST substantial block of text
    # (Claude's response is usually the last block before the new prompt)
    if not natural_lines:
        return ""

    # Take last N lines (max 20) that form a coherent response
    result_lines = natural_lines[-20:]

    # Join and clean up
    result = '\n'.join(result_lines)

    # Final cleanup: remove multiple spaces/newlines
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()

    # Verify we have meaningful content
    if len(result) < 20:
        return ""

    # Check it's not just garbage (should be mostly letters and spaces)
    letter_space_count = sum(1 for c in result if c.isalpha() or c.isspace() or c in '.,!?;:')
    if len(result) > 0 and letter_space_count / len(result) < 0.7:
        return ""

    return result


# Convenience function
def clean_for_tts(text: str, language: str = "pl_PL", use_dictionary: bool = True) -> str:
    """
    Clean text for TTS reading.

    Args:
        text: Raw text from terminal
        language: Language code for dictionary
        use_dictionary: Whether to filter non-dictionary words

    Returns:
        Cleaned text suitable for TTS
    """
    cleaner = TextCleanerForTTS(language)
    return cleaner.clean(text, use_dictionary)

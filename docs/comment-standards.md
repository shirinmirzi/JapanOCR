# Code Documentation and Comment Standards

This document defines the commenting and documentation standards for the Japan OCR Tool.
All contributors must follow these standards when writing or modifying code.

---

## Core Principles

1. **Purpose-Driven** — Comments explain *why*, not *what*.
2. **Human-Readable** — Write for developers, not machines.
3. **Concise** — Maximum clarity with minimum words.
4. **Consistent** — Uniform style across all files.
5. **Valuable** — Every comment adds genuine understanding.

---

## Python Standards

### File Headers

Every Python file must begin with a module docstring:

```python
"""
Japan OCR Tool - [Component Name]

[Brief description of file purpose and responsibilities]

Key Features:
- Feature 1: Brief description
- Feature 2: Brief description

Dependencies: [Major external dependencies]
Author: SHIRIN MIRZI M K
"""
```

### Function / Method Docstrings

Use full docstrings for all public functions:

```python
def function_name(param1: type, param2: type) -> return_type:
    """
    Single line describing what the function accomplishes.

    Args:
        param1: Clear description of what this parameter does.
        param2: Description including expected format/range.

    Returns:
        Description of return value and its structure.

    Raises:
        SpecificError: When this specific condition occurs.
    """
```

### Class Docstrings

```python
class ClassName:
    """
    Single line describing the class purpose.

    Attributes:
        attribute1: Description of what this stores.
        attribute2: Description including data type and purpose.
    """
```

### Inline Comments

Write comments that explain *why* a decision was made:

```python
# Good: explains non-obvious behaviour
# Include legacy entries that predate module tagging.
conditions.append("(metadata->>'module' = %s OR metadata->>'module' IS NULL)")

# Good: clarifies a business rule
# A non-numeric destination_cd signals a DoNotSend routing rule.
if not re.fullmatch(r'\d+', destination_cd):
    return customer_code, True
```

Avoid obvious comments:

```python
# Bad
x = 5  # Set x to 5
for item in items:  # Loop through items
```

### Section Separators

Use separators to group related blocks in long files:

```python
# =============================================================================
# CONFIGURATION AND SETUP
# =============================================================================

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
```

### TODO / FIXME / NOTE Tags

```python
# TODO: Implement pagination for large datasets (Issue #123)
# FIXME: Handle edge case where batch number is missing (Priority: High)
# NOTE: This algorithm assumes sorted input.
```

---

## JavaScript / React Standards

### File Headers (JSDoc block)

Every `.js` / `.jsx` file must begin with:

```javascript
/**
 * Japan OCR Tool - [Component Name]
 *
 * [Brief description of file purpose]
 *
 * Key Features:
 * - Feature 1: Brief description
 * - Feature 2: Brief description
 *
 * Dependencies: [Major dependencies]
 * Author: SHIRIN MIRZI M K
 */
```

### Component Documentation

```javascript
/**
 * Renders the full-page login screen with sign-in button.
 *
 * @param {Object} props - Component properties
 * @param {Function} props.onSuccess - Callback after successful login
 * @returns {JSX.Element} Full-page login screen
 */
export default function LoginPage({ onSuccess }) {
```

### Function Documentation

```javascript
/**
 * Builds the Authorization header for the current session.
 * Uses a static dev-token when dev-login is active to avoid MSAL overhead.
 *
 * @returns {Promise<Object>} Header object with Authorization field, or {}
 */
async function getAuthHeader() {
```

---

## What NOT to Comment

Remove these comment types:

```python
# Bad – obvious
users = []  # Initialize empty list of users
return result  # Return the result

# Bad – commented-out code (delete it)
# old_function_call()
# if legacy_condition:
#     do_old_thing()

# Bad – redundant
for user in all_users:  # Loop through all users
    users.append(user)  # Add user to list
```

---

## Formatting Rules

| Rule | Requirement |
|---|---|
| Line length | Keep comments under 80 characters where practical |
| Indentation | Match surrounding code |
| Spacing | One space after `#` or `//` |
| Capitalization | Start with a capital letter |
| Sentences | End with a period for full sentences |

---

## Review Checklist

Before committing code, verify:

- [ ] All comments add genuine value
- [ ] No obvious or redundant comments
- [ ] Consistent formatting and style
- [ ] TODOs include context and priority
- [ ] Complex logic is well-explained
- [ ] Public APIs have complete docstrings
- [ ] File headers are present in all files

---

Author: SHIRIN MIRZI M K

# Simple Python Calculator

Build a command-line calculator that evaluates mathematical expressions with proper operator precedence.

## Requirements

### Core Functionality
- Accept mathematical expressions as input (e.g., "2 + 3 * 4")
- Support basic operators: `+`, `-`, `*`, `/`, `**` (power), `//` (floor division), `%` (modulo)
- Properly handle operator precedence (multiplication before addition, etc.)
- Return accurate results

### Error Handling
- Validate input expressions
- Handle division by zero gracefully
- Report invalid syntax clearly

### Interface
- Simple command-line REPL (Read-Eval-Print Loop)
- Show results immediately after each calculation
- Allow user to exit with "quit" or "exit" command
- Show a help message on startup

### Example Session
```
Calculator v1.0
Type expressions or 'quit' to exit
> 2 + 3 * 4
Result: 14

> 10 / 2 - 3
Result: 2.0

> 2 ** 8
Result: 256

> 10 / 0
Error: Cannot divide by zero

> quit
Goodbye!
```

Keep it simple, robust, and focused on correctness.

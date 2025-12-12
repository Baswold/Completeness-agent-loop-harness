# Command-Line Task Manager

Build a simple but functional command-line task management application with:

## Core Features
- **Add tasks**: Users can add new tasks with a description
- **List tasks**: Display all tasks with status (pending/done)
- **Mark complete**: Mark tasks as done
- **Delete tasks**: Remove completed tasks
- **Persistence**: Save tasks to a JSON file so they persist between sessions

## Technical Requirements
- Pure Python (no external dependencies except what's in stdlib)
- Single file implementation (main.py)
- JSON file for storage (tasks.json)
- Simple CLI interface with numbered menu
- Error handling for invalid input
- Color-coded output (using ANSI codes)

## Example Usage
```
$ python tasks.py
=== Task Manager ===
Tasks: [1] Do laundry (pending) [2] Buy groceries (pending)

1. Add task
2. List tasks
3. Mark task complete
4. Delete task
5. Exit

Choose action: 1
Enter task description: Fix bugs
✓ Task added

Choose action: 3
Enter task number: 1
✓ Task marked complete

Choose action: 5
Goodbye!
```

That's it - simple, functional, and complete!

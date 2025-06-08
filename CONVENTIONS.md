# Coding Conventions

## Test-Driven Development (TDD)

We follow a strict Test-Driven Development approach for all new features and bug fixes. The workflow is as follows:

1.  **Red:** Write a test case that defines the desired functionality or reproduces the bug. Verify that this test fails because the code doesn't exist or is incorrect.
2.  **Green:** Write the *minimum* amount of code necessary to make the failing test pass. Do not worry about optimal code at this stage.
3.  **Refactor:** Improve the code written in the "Green" step. Clean up duplication, improve clarity, and optimize performance *while ensuring all tests continue to pass*.

Adhering to this cycle ensures that all code is testable and tested, reduces bugs, and improves design. Always say what stage of the workflow you're in.

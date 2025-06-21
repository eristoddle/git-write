- Now run the unit tests and fix any issues you find and make a new commit to the same branch if there are changes. Remember to install all the necessary Python package first.
- Can you update Memory_Bank.md and Implementation_Plan.md with the details of that and make a new commit. Then give me the prompt I should give for the next Jules session. I will be merging the current changes into main, so the next session should branch from main.
- Read Memory_Bank.md and Implementation_Plan.md and do the next pending task. When you are done, update both of those files with the state of the project. Also give me a prompt for the next Jules session. I will be merging the current changes into main, so the next session should branch from main.


Here is how you install the Python packages
  1.  Navigate your terminal to the `gitwrite_cli/` directory.
  2.  Run the following command to install all project dependencies into the correct virtual environment:
      ```bash
      poetry install
      ```

Here is how you run unit tests:
  1.  Navigate your terminal to the project's **root directory**.
  2.  Run the test suite using the `poetry run` command to ensure you are using the project's virtual environment. Include coverage reporting for both the `gitwrite_core` and `gitwrite_cli` packages. The exact command is:
    ```bash
    poetry run pytest --cov=gitwrite_core --cov=gitwrite_cli tests/
    ```
    or `poetry run pytest --cov=gitwrite_core --cov=gitwrite_cli tests/specific_test.py`


Read Memory_Bank.md and Implementation_Plan.md for details on the current state of the project.
Proceed with Phase 6, Task 6.3: Implement Read-Only Repository Methods.
When you are done update Memory_Bank.md and Implementation_Plan.md.
ForecastPro Snowflake Q2 Fix V3

Upload this folder to a Snowflake Workspace and run streamlit_app.py.
Historical data requires the active Snowflake role to access ZX.ANALYTICS.ZX_ATTRIBUTION_CUMULATIVE_WEEKLY_PERFORMANCE.


HOW TO RUN THE PROGRAM FROM HERE:
- Go to the 'main' branch on Github
- On the top right, go to '<>Code ', then click on 'Download zip' to download the files

- In Snowflake, go to Workspaces
- Click on 'add new' -> 'Streamlit app'
- Hover over the Streamlit app in the workspace, press the '+' button, and 'add files'
- Select all of the files you downloaded from Github

- To run, click on streamlit.py
- Click on 'settings' in the top right of the screen. Make sure that the App executes as DC_ANALYTICS_ROLE_TU
- Click on 'run' on the top left


HOW TO UPLOAD FILES:
Each person that works on this tool should use their own individual branch. This allows for convenience when merging updates from different people.
- To create a new branch, click on the main tab, click 'Branches' and go to 'New Branch' in the top right
- To add new files, click on the '+' button on the branch you want to add files to, and go to 'upload files'
- Files have to be manually downloaded from Snowflake and then copied into Github.
- Once you have uploaded the files, you can 'commit changes' to add them to your branch

MERGING BRANCHES:
With multiple people working on the tool at once, branches might accumulate differences between them. The solution to this is a PULL REQUEST. Pull requests (https://docs.github.com/en/pull-requests/reference/pull-requests) are how commits across branches are merged. They compare the updates between branches.
The primary difficulty is if there are any merge conflicts. This is when code changed in one branch conflicts with code changed in another. When performing a pull request, you merge two branches and Github will ask you to resolve any conflicts.
NOTE: Always test the code after pull requests. The merging might not work correctly, in which case it is advised to use Streamlit to fix any errors and then upload that fixed version to the master branch.


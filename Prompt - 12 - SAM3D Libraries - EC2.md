1 - The instance is: i-042ca5d5485788c84 . 

2 - You can try to use ssh directly (not sure if ec2-user or ubuntu), but we have been using aws SSM. More below.

3 - Regarding the directroy you should work on, to test the installes of the referred libraries, use a temporary directory at first, for your investigation. Later we can do the installs in the container directory.

4 - For the other answers, read the list of documents below to learn what have been done so far: 

<base_documents>
    ~/docs/Gen3D - Architecture - 1.2.md
    ~/docs/Gen3D - Implementation Plan - 1.2.md
    ~/docs/SAM3-SAM3D - Arch - 1.2.mermaid
    ~/DEPLOYMENT_EXECUTION_REPORT.md
    ~/FINAL_DEPLOYMENT_REPORT.md
    ~/10 - PREVENTIVE-SOLUTIONS.md
    ~/12 - LOCAL-DEPLOYMENT-PLAN.md
    ~/13 - LOCAL-DEPLOYMENT-EXECUTION-REPORT.md
    ~/13 - PRODUCTION-DEPLOYMENT-PLAN.md

    # Highly Relevant:
    ~/14 - SAGEMAKER-DEPLOYMENT-REPORT.md
    ~/15 - END-TO-END-TEST-FAILURE-REPORT.md
    ~/15 - END-TO-END-TEST-FAILURE-REPORT-SUMMARY.md
</documents>

5 - Do let me know what you find out about the environment.



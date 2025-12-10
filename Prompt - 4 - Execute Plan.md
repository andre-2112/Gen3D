# Tasks

1 - Read this entire document and then start deploying the whole Gen3D framework and web app, on the Gemini3d aws account. Now.

2 - The HuggingFace steps are no longer necessary, as I already prefetched the models. See below.

  2.1 - Adjust all deployment scripts to fetch the SAM3 and SAM3D models DIRECTLY from the respective s3://gen3d-data-bucket/models/sam3 and s3://gen3d-data-bucket/models/sam3d folders. 

==
aws sts get-caller-identity --query Account --output text --profile genesis3d
Account: 211050572089

==
  1. Access web app at: http://gen3d-data-bucket.s3-website-us-east-1.amazonaws.com
  2. Sign in with test credentials: test@gen3d.example.com / TestPass123!
  3. Test with provided images: coil.jpg, pump.jpg, or chiller.jpg

==
Use the following HuggingFace token for deployment and testing: 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

  - Adjust all files that refers to the HuggingFace token.

For HuggingFace, replace all references of the huggingface-cli command for the equivalent "hf" cli commands
  - All files indie the ~/deployment folder.
  - Do not just replace the command, but do adapt the command as there might might differences in the paramenters.

# Gen3D - User Guide v1.0

## Welcome to Gen3D

Gen3D is an AI-powered service that transforms 2D images into high-quality 3D meshes. Using Meta's cutting-edge SAM 3D Objects technology, Gen3D extracts objects from your photos and creates detailed 3D models complete with textures and accurate geometry.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Using the Web Interface](#using-the-web-interface)
3. [Understanding Your Results](#understanding-your-results)
4. [Opening 3D Files](#opening-3d-files)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)
7. [API Usage (Advanced)](#api-usage-advanced)
8. [Frequently Asked Questions](#frequently-asked-questions)
9. [Support](#support)

---

## Getting Started

### What You Need

1. **User ID**: Your unique identifier (provided during registration)
2. **Email Address**: To receive notifications and download links
3. **Images**: Photos containing objects you want to convert to 3D
4. **Web Browser**: Modern browser (Chrome, Firefox, Safari, Edge)

### What Gen3D Does

Gen3D takes a 2D image and an object selection, then:
- Analyzes the object's shape, texture, and spatial layout
- Reconstructs a full 3D model with geometry
- Applies realistic textures
- Handles occlusions and complex poses
- Delivers a downloadable .ply file

### What Gen3D Works Best With

Gen3D excels at:
- Everyday objects (furniture, toys, electronics, etc.)
- Items with clear boundaries
- Objects in natural photographs
- Items with texture and color variation
- Single or multiple distinct objects in a scene

Gen3D may struggle with:
- Completely transparent or reflective objects
- Objects without clear edges
- Very small or distant objects
- Images with extreme blur or low quality

---

## Using the Web Interface

### Step 1: Access the Web Interface

Open your web browser and navigate to:
```
http://gen3d-data-bucket.s3-website-us-east-1.amazonaws.com
```

You should see the Gen3D interface with a purple gradient background and an upload area.

### Step 2: Enter Your User ID

In the "User ID" field at the top, enter your unique identifier:
```
Example: user123
```

**Important**: Keep your User ID consistent across sessions to access your processing history.

### Step 3: Upload an Image

You can upload an image in two ways:

**Method 1: Drag and Drop**
1. Open your file explorer
2. Drag your image file onto the upload area
3. Release to upload

**Method 2: Click to Select**
1. Click anywhere in the upload area
2. Browse to your image file
3. Select and open

**Supported Formats**: PNG, JPG, JPEG

**Recommended Image Specs**:
- Resolution: 800x600 to 4096x4096 pixels
- File Size: Under 10 MB
- Format: PNG or JPG
- Quality: Clear, well-lit, in-focus photos

### Step 4: Select Objects

Once your image loads:

1. **Draw a Bounding Box**:
   - Click and hold at one corner of the object
   - Drag to the opposite corner
   - Release to complete the box

2. **Multiple Objects**:
   - Draw additional boxes for more objects
   - Each object will be processed separately
   - Maximum recommended: 5 objects per image

3. **Review Your Selections**:
   - Green boxes show confirmed selections
   - Red box shows current drawing
   - List below canvas shows all selections

4. **Delete a Selection**:
   - Click "Delete" next to any object in the list
   - Or click "Clear Selection" to remove all boxes

**Tips for Good Selections**:
- Include the entire object within the box
- Add a small margin around the edges
- Avoid including too much background
- Make sure the object is clearly visible

### Step 5: Process Your Image

1. Review your bounding boxes
2. Ensure your User ID is correct
3. Click the **"Process Image"** button
4. Wait for the confirmation message

You should see:
```
Success! X object(s) queued for processing.
You will receive an email when your 3D meshes are ready.
```

### Step 6: Check Your Email

Processing typically takes **2-10 minutes** per object, depending on complexity.

You'll receive an email at the address associated with your User ID containing:
- Download link for your 3D mesh (.ply file)
- File size and details
- Link expiration time (24 hours)
- Instructions for opening the file

**Email Subject**: "Your 3D Mesh is Ready!"

---

## Understanding Your Results

### What You Receive

**File Format**: .ply (Polygon File Format / Stanford Triangle Format)

**File Contents**:
- 3D vertex positions (geometry)
- Face/triangle definitions
- Texture colors
- Normal vectors (for smooth rendering)

**File Size**: Typically 5-50 MB depending on complexity

### Quality Factors

The quality of your 3D mesh depends on:

1. **Input Image Quality**:
   - Higher resolution = better detail
   - Good lighting = better texture
   - Sharp focus = better geometry

2. **Object Characteristics**:
   - Clear edges = cleaner mesh
   - Visible texture = better appearance
   - Distinct from background = better separation

3. **Viewing Angle**:
   - Multiple angles visible = more complete model
   - Single angle = some surfaces may be estimated

### What to Expect

**Strengths**:
- Accurate overall shape and proportions
- Realistic textures from visible surfaces
- Good handling of occlusions
- Natural-looking results

**Limitations**:
- Backside of objects may be approximated
- Completely hidden surfaces are estimated
- Very fine details may be smoothed
- Transparent/reflective surfaces may vary

---

## Opening 3D Files

### Recommended Software

#### Blender (Free, Cross-Platform)
**Best for**: Editing, rendering, advanced use

1. Download from [blender.org](https://www.blender.org)
2. Install and open Blender
3. Go to File > Import > Stanford (.ply)
4. Select your downloaded .ply file
5. Navigate with middle mouse button

**Viewing Tips**:
- Scroll to zoom
- Middle mouse drag to rotate
- Shift + middle mouse to pan
- Press 'Z' for viewing modes (solid, material, rendered)

#### MeshLab (Free, Cross-Platform)
**Best for**: Viewing, basic editing, measurement

1. Download from [meshlab.net](https://www.meshlab.net)
2. Install and open MeshLab
3. Go to File > Import Mesh
4. Select your .ply file
5. Use mouse to rotate and inspect

**Useful Features**:
- Measuring tools
- Filters for smoothing
- Export to other formats
- Vertex/face inspection

#### Windows 3D Viewer (Windows 10/11)
**Best for**: Quick viewing on Windows

1. Locate your .ply file in File Explorer
2. Right-click > Open with > 3D Viewer
3. Rotate and zoom with mouse
4. Very simple but limited features

#### Online Viewers
**Best for**: Quick viewing without installation

- [3DViewer.net](https://3dviewer.net)
- [ViewSTL.com](https://viewstl.com)

**Note**: Upload files at your own discretion regarding privacy.

### Converting to Other Formats

Use Blender or MeshLab to export to:
- **.obj**: Widely supported, with separate texture file
- **.stl**: For 3D printing (no color)
- **.fbx**: For game engines (Unity, Unreal)
- **.gltf**: For web 3D (Three.js)
- **.dae**: For CAD software

---

## Best Practices

### Taking Great Photos

1. **Lighting**:
   - Use natural daylight or bright, even lighting
   - Avoid harsh shadows
   - Illuminate all sides of the object
   - Avoid strong backlighting

2. **Background**:
   - Use plain, contrasting backgrounds when possible
   - Avoid busy or cluttered backgrounds
   - Clear separation helps accuracy

3. **Camera Position**:
   - Photograph at eye-level with the object
   - Include the entire object in frame
   - Keep camera steady (avoid blur)
   - Take multiple angles for reference

4. **Object Setup**:
   - Place object on neutral surface
   - Ensure object is stable
   - Remove unwanted items from scene
   - Consider scale reference (optional)

### Selecting Objects

1. **Precise Boundaries**:
   - Draw boxes tight to object edges
   - Include all parts you want extracted
   - Exclude as much background as possible

2. **Multiple Objects**:
   - Process similar objects together
   - Keep objects separated in image
   - Avoid overlapping selections

3. **Complex Objects**:
   - For very complex items, try multiple views
   - Consider breaking into components
   - Focus on main recognizable features

### Processing Tips

1. **Batch Processing**:
   - Upload multiple objects from one image
   - Process similar items together
   - Keep track of your User ID

2. **Iterations**:
   - If result isn't perfect, try again with different selection
   - Experiment with different photos
   - Adjust lighting or background

3. **File Management**:
   - Download files promptly (24-hour expiration)
   - Rename files descriptively
   - Keep original photos for reference

---

## Troubleshooting

### Upload Issues

**Problem**: "File upload failed"
- **Solution**: Check file size (must be under 10 MB)
- **Solution**: Verify file format (PNG or JPG)
- **Solution**: Try a different browser
- **Solution**: Check internet connection

**Problem**: "Invalid User ID"
- **Solution**: Ensure User ID has no spaces or special characters
- **Solution**: Contact admin if you don't have a User ID
- **Solution**: Use the same format as provided

### Processing Issues

**Problem**: "No email received"
- **Check**: Spam/junk folder
- **Check**: Email associated with User ID is correct
- **Wait**: Processing can take up to 10 minutes
- **Contact**: Support if >30 minutes with no email

**Problem**: "Download link expired"
- **Solution**: Links expire after 24 hours
- **Solution**: Reprocess the image to get a new link
- **Note**: Original files are not stored indefinitely

**Problem**: "Processing failed" email
- **Cause**: Image may be corrupted
- **Cause**: Object selection too small or unclear
- **Solution**: Try a different image
- **Solution**: Ensure object is clearly visible
- **Solution**: Check image quality

### Quality Issues

**Problem**: "Mesh is incomplete or missing surfaces"
- **Explanation**: Hidden surfaces are estimated
- **Solution**: Try a photo from a different angle
- **Solution**: Ensure object is fully visible in image

**Problem**: "Texture is blurry or incorrect"
- **Cause**: Low image resolution
- **Cause**: Poor lighting in original photo
- **Solution**: Use higher resolution images
- **Solution**: Retake photo with better lighting

**Problem**: "Mesh is too rough or jagged"
- **Cause**: Object edges not clear in image
- **Solution**: Use MeshLab or Blender smoothing filters
- **Solution**: Retake photo with clearer boundaries

**Problem**: "File won't open in my software"
- **Check**: Software supports .ply format
- **Try**: Different software (Blender always works)
- **Try**: Re-download the file
- **Contact**: Support if file appears corrupted

---

## API Usage (Advanced)

For developers and automated workflows, Gen3D can be accessed programmatically.

### Direct S3 Upload

Upload images directly to S3 using AWS SDK or CLI:

```bash
# Using AWS CLI
aws s3 cp my_image.png s3://gen3d-data-bucket/users/YOUR_USER_ID/input/my_image.png
```

```python
# Using Python boto3
import boto3

s3 = boto3.client('s3')
s3.upload_file(
    'my_image.png',
    'gen3d-data-bucket',
    'users/YOUR_USER_ID/input/my_image.png'
)
```

### Monitoring Results

Poll the output folder for results:

```bash
# Check for output files
aws s3 ls s3://gen3d-data-bucket/users/YOUR_USER_ID/output/
```

### Download Results

```bash
# Download specific file
aws s3 cp s3://gen3d-data-bucket/users/YOUR_USER_ID/output/mesh.ply ./mesh.ply

# Download all outputs
aws s3 sync s3://gen3d-data-bucket/users/YOUR_USER_ID/output/ ./outputs/
```

### Authentication

**Note**: API access requires proper AWS credentials configured:
- IAM user with appropriate permissions
- Access key and secret key configured in AWS CLI
- Or using IAM roles in EC2/Lambda environments

**Contact**: info@2112-lab.com for API access setup

---

## Frequently Asked Questions

### General Questions

**Q: How much does Gen3D cost?**
A: Pricing depends on your usage tier. Contact info@2112-lab.com for details.

**Q: How long does processing take?**
A: Typically 2-10 minutes per object, depending on image complexity and current queue.

**Q: Is my data private?**
A: Yes, files are stored in user-specific folders accessible only to you. Files are automatically deleted after 90 days.

**Q: Can I process videos?**
A: Currently, Gen3D only supports static images. Extract frames from videos and process individually.

**Q: What's the maximum file size?**
A: 10 MB per image. For larger files, resize or compress before uploading.

### Technical Questions

**Q: What is a .ply file?**
A: PLY (Polygon File Format) is a standard 3D mesh format containing vertices, faces, and color data.

**Q: Can I edit the 3D models?**
A: Yes! Use software like Blender for full editing capabilities.

**Q: Can I 3D print the results?**
A: Yes, export to .stl format using Blender or MeshLab, then send to your 3D printer software.

**Q: What about copyright?**
A: You retain all rights to your images and generated 3D models. Don't upload copyrighted images without permission.

**Q: Can I use Gen3D commercially?**
A: Commercial use is permitted. Check the SAM license terms and your service agreement.

### Workflow Questions

**Q: Can I process multiple objects at once?**
A: Yes, draw multiple bounding boxes on a single image. Each will be processed separately.

**Q: How do I organize my projects?**
A: Use descriptive filenames and maintain consistent User ID. Consider creating a folder structure locally for downloads.

**Q: Can I reprocess an object?**
A: Yes, upload the same image again with adjusted selections or try a different photo.

**Q: Do you store my images permanently?**
A: No, images and outputs are deleted after 90 days as per our retention policy.

**Q: Can I get notifications on mobile?**
A: Yes, check your email on mobile. Future updates may include SMS notifications.

---

## Support

### Getting Help

**Email Support**: info@2112-lab.com
- Response time: 1-2 business days
- Include your User ID and description of issue
- Attach screenshots if helpful

**Documentation**: Refer to this guide for common issues

**System Status**: Check AWS Service Health Dashboard for outages

### Reporting Issues

When reporting issues, please include:

1. **User ID**: Your unique identifier
2. **Timestamp**: When the issue occurred
3. **Image Details**: Resolution, format, file size
4. **Browser**: Type and version
5. **Error Messages**: Exact text of any errors
6. **Steps to Reproduce**: What you did before the issue

### Feature Requests

We welcome your suggestions! Email info@2112-lab.com with:
- Feature description
- Use case / why it's needed
- Priority for your workflow

### Updates and Announcements

- Check your email for service updates
- Major features will be announced via email
- System maintenance notifications sent 48 hours in advance

---

## Tips for Success

### For Best Results

1. **Start Simple**: Begin with clear, simple objects to understand the process
2. **Experiment**: Try different photos, angles, and selections
3. **Iterate**: Don't expect perfection on first try
4. **Learn Your Tools**: Spend time learning Blender or MeshLab for post-processing
5. **Plan Ahead**: Consider how you'll use the 3D models before shooting

### Common Use Cases

**Product Photography**:
- Create 3D models for e-commerce
- Show products from all angles
- Enhance online catalogs

**Education**:
- Create 3D models for teaching
- Document artifacts and specimens
- Build interactive learning materials

**Gaming and VR**:
- Generate game assets from real objects
- Create environment props
- Populate virtual worlds

**3D Printing**:
- Replicate physical objects
- Create modified versions
- Archive items digitally

**Architecture and Design**:
- Document existing objects
- Create concept visualizations
- Build material libraries

---

## What's Next?

### Future Features

Upcoming enhancements to Gen3D:
- Real-time progress updates
- In-browser 3D preview
- Multiple export formats
- Advanced editing tools
- Mobile app
- Batch processing improvements

### Learning Resources

**3D Modeling Tutorials**:
- [Blender Guru YouTube Channel](https://www.youtube.com/user/AndrewPPrice)
- [Blender Official Tutorials](https://www.blender.org/support/tutorials/)

**3D Printing**:
- [All3DP Guides](https://all3dp.com)
- [Thingiverse](https://www.thingiverse.com)

**Computer Vision**:
- [Meta AI Research](https://ai.facebook.com)
- [SAM 3D Paper](https://arxiv.org/abs/2511.16624)

---

## Terms and Conditions

### Service Agreement

By using Gen3D, you agree to:
- Use the service responsibly
- Not upload illegal or copyrighted content
- Accept that results may vary
- Understand data retention policies (90-day deletion)

### Privacy

- Your data is stored securely on AWS
- Files are user-isolated
- No data sharing with third parties
- Admin access for support only

### Liability

- Gen3D is provided "as-is"
- No guarantees on output quality
- Not liable for downstream use of 3D models
- Service availability not guaranteed

---

## Contact Information

**Technical Support**: info@2112-lab.com

**Service Provider**: Genesis3D

**Service Name**: Gen3D

**Version**: 1.0

**Last Updated**: Initial release

---

## Quick Reference Card

### Upload Checklist
- [ ] User ID entered
- [ ] Image uploaded (PNG/JPG, <10MB)
- [ ] Object(s) selected with bounding boxes
- [ ] "Process Image" clicked
- [ ] Confirmation message received

### What to Expect
- **Processing Time**: 2-10 minutes
- **Email**: Download link (expires in 24 hours)
- **File Type**: .ply (3D mesh)
- **File Size**: 5-50 MB typical

### Quick Troubleshooting
- No email? → Check spam folder, wait 10 minutes
- Can't open file? → Use Blender or MeshLab
- Poor quality? → Try better photo, clearer selection
- Upload fails? → Check file size/format

---

Thank you for using Gen3D! We're excited to see what you create.

For assistance: info@2112-lab.com

# AWS Lambda Image Compression

Convert images uploaded to Amazon S3 into WebP format using AWS Lambda and Pillow.

## How it works

1. Upload an image to the S3 bucket's `input/` folder.
2. S3 triggers the Lambda function.
3. Lambda downloads and opens the image using Pillow.
4. The function resizes the image to fit within **1280 × 720** while preserving its aspect ratio.
5. The function applies a watermark and converts the image to WebP.
6. Lambda uploads the result to the `output/` folder with the `.webp` extension.

> Supported formats depend on Pillow and the installed codecs. Animated GIFs are generally reduced to a single frame by basic image-processing code. SVG and HEIC/HEIF require additional handling.

## AWS configuration

### 1. Lambda runtime and handler

- Runtime: **Python 3.12** (or another runtime explicitly supported by Lambda and matched by your package)
- Architecture: **x86_64** if dependencies were packaged for x86_64
- Handler: `lambda_function.lambda_handler`
- Deployment: ZIP file containing the function code and dependencies at the ZIP root (no Lambda Layer required)

### 2. Package dependencies without a Layer

Build the deployment package for the same Python version, operating system compatibility, and architecture as the Lambda function. Example for Python 3.12 and x86_64, from Ubuntu/WSL:

```bash
mkdir -p package

python -m pip install \
  --platform manylinux2014_x86_64 \
  --target package \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  boto3 Pillow

cp lambda_function.py package/
cd package
zip -r ../image-processing-lambda.zip .
cd ..
```

The ZIP should contain `lambda_function.py`, `PIL/`, and the installed dependency folders directly at its root. Do not ZIP the enclosing `package/` directory or include your virtual environment.

If using Python 3.14 in Lambda instead, select Python 3.14 in the Lambda runtime and change `--python-version 3.14`. Ensure Pillow wheels are available for the chosen runtime and architecture.

### 3. Lambda timeout and memory

For image processing, start with:

- Timeout: **30 seconds**
- Memory: **512 MB**

Increase these if large images still take too long or use more memory. The initial 3-second timeout caused the function to stop before finishing.

### 4. S3 permissions

The Lambda execution role needs permission to read input images and write converted images. Scope permissions to the relevant bucket paths:

- `s3:GetObject` on `arn:aws:s3:::YOUR-BUCKET-NAME/input/*`
- `s3:PutObject` on `arn:aws:s3:::YOUR-BUCKET-NAME/output/*`

Keep the standard CloudWatch logging permissions (for example, `AWSLambdaBasicExecutionRole`).

### 5. S3 trigger

Configure an S3 **Object Created** trigger for the same bucket and Region, with the prefix set to:

```text
input/
```

Do not trigger on the entire bucket. Restricting the trigger to `input/` prevents output files from triggering the function repeatedly.

## Troubleshooting: no files in `output/`

The CloudWatch logs showed:

```text
Duration: 3000.00 ms
Memory Size: 128 MB
Status: timeout
```

This means the Lambda execution exceeded its 3-second timeout. It does not, by itself, prove an S3 permission problem.

1. Set the timeout to 30 seconds and memory to 512 MB.
2. Add log messages after downloading, opening, converting, and uploading the image.
3. Deploy the updated code and upload a **new test image** to `input/`.
4. Open **Lambda → Monitor → View CloudWatch logs** and inspect the newest log stream.
5. Find the last log message to identify which operation did not finish.
6. If upload fails, verify the execution role's `s3:PutObject` permission and check the exception in CloudWatch.

Example diagnostic messages to add around your existing code:

```python
print("Starting image download")
# Download image
print("Image downloaded successfully")

# Open and process image
print("Image opened successfully:", img.format, img.size)

print("Starting WebP conversion")
# Convert image to WebP
print("WebP conversion completed")

print("Uploading to:", output_key)
# Upload to S3
print("Upload completed successfully")
```

Keep your existing resize and watermark code when adding these logs.

## Testing checklist

- [ ] Lambda runtime, handler, and package versions match.
- [ ] Lambda timeout is 30 seconds and memory is 512 MB (or higher if needed).
- [ ] Execution role allows `GetObject` from `input/` and `PutObject` to `output/`.
- [ ] S3 trigger uses the `input/` prefix.
- [ ] Upload a test image to `input/`.
- [ ] Confirm a `.webp` file appears in `output/`.
- [ ] Confirm CloudWatch logs show `Upload completed successfully`.

## Notes

- Output filenames should end in `.webp`, and uploaded objects should use `ContentType="image/webp"`.
- Use `unquote_plus` when decoding S3 event object keys, because S3 event keys can be URL-encoded.
- Validate uploaded files and handle unsupported formats with `try/except`.
- AWS charges can apply to Lambda invocations, S3 storage/requests, and CloudWatch Logs. Remove resources you no longer need.

import boto3
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import unquote_plus
import io
import os

# Create an S3 client to download and upload images
s3 = boto3.client("s3")


def lambda_handler(event, context):
    # Set the output image format
    output_format = "WEBP"

    # Read the first S3 event record
    record = event["Records"][0]

    # Get the S3 bucket name
    bucket_name = record["s3"]["bucket"]["name"]

    # Get and decode the uploaded object's key
    object_key = unquote_plus(record["s3"]["object"]["key"])

    # Log the bucket and object key in CloudWatch
    print("Bucket:", bucket_name)
    print("Object:", object_key)

    # Only process files uploaded to input/
    if not object_key.startswith("input/"):
        return {
            "statusCode": 400,
            "body": "File not in the input folder."
        }

    try:
        # Download the original image from S3
        s3_response = s3.get_object(
            Bucket=bucket_name,
            Key=object_key
        )

        # Read the image bytes into memory
        image_content = s3_response["Body"].read()

        # Open the image and convert it to RGBA
        # RGBA supports images with transparency
        with Image.open(io.BytesIO(image_content)) as original:
            img = original.convert("RGBA")

            # Fit the image within 1280x720 without stretching it
            img.thumbnail((1280, 720), Image.Resampling.LANCZOS)

        # Create a transparent layer for the watermark
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font = ImageFont.load_default()

        # Define the watermark text
        watermark_text = "https://lepczynski.it"

        # Calculate the size of the watermark text
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Position the watermark near the bottom-right corner
        x = max(5, img.width - text_width - 10)
        y = max(5, img.height - text_height - 10)

        # Draw the watermark with partial transparency
        draw.text(
            (x, y),
            watermark_text,
            font=font,
            fill=(255, 255, 255, 160),
            stroke_width=1,
            stroke_fill=(0, 0, 0, 120)
        )

        # Combine the image and watermark
        img = Image.alpha_composite(img, overlay)

        # Encode the processed image in memory as WebP
        buffer = io.BytesIO()
        img.save(buffer, format=output_format, quality=85)

        # Remove input/ and the original extension from the key
        relative_path = object_key[len("input/"):]
        filename = os.path.splitext(relative_path)[0]

        # Build the output key
        output_key = f"output/{filename}.webp"

        # Upload the processed image to the same S3 bucket
        s3.put_object(
            Bucket=bucket_name,
            Key=output_key,
            Body=buffer.getvalue(),
            ContentType="image/webp"
        )

        # Return a success response
        return {
            "statusCode": 200,
            "body": f"Image processed successfully: {output_key}"
        }

    except Exception as error:
        # Log the error and mark the invocation as failed
        print("Image processing failed:", str(error))
        raise
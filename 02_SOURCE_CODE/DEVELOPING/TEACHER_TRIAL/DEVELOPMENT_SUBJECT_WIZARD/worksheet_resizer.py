
# -*- coding: utf-8 -*-
"""
SAINI WORKSHEET EXACT PIXEL RESIZER

2 Examples: 2170 x 550 pixels
4 Examples: 2170 x 700 pixels

IMPORTANT:
- Stretches images to exact dimensions.
- Aspect ratio is NOT preserved.
- No white padding is added.
- Original images are not modified.
- Output images are saved in a separate folder.

Install:
    python -m pip install Pillow

Run:
    python worksheet_resizer.py "INPUT_FOLDER" "OUTPUT_FOLDER" 2
    python worksheet_resizer.py "INPUT_FOLDER" "OUTPUT_FOLDER" 4
"""

import argparse
import sys
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError

# ============== SETTINGS ==============

TARGET_WIDTH = 2170

HEIGHT_FOR_2_EXAMPLES = 550
HEIGHT_FOR_4_EXAMPLES = 700

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
}

JPEG_QUALITY = 95

# ======================================


def get_target_height(examples):
    if examples == 2:
        return HEIGHT_FOR_2_EXAMPLES

    if examples == 4:
        return HEIGHT_FOR_4_EXAMPLES

    raise ValueError("Examples must be 2 or 4.")


def resize_exact(image, width, height):
    """
    Force the image to exact dimensions.
    Stretching/skewing is allowed.
    No padding or cropping is performed.
    """

    image = ImageOps.exif_transpose(image)

    # Preserve transparency for PNG and WEBP.
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        image = image.convert("RGBA")
    else:
        image = image.convert("RGB")

    # Direct resize: aspect ratio intentionally changes.
    image = image.resize(
        (width, height),
        Image.Resampling.LANCZOS
    )

    return image


def save_image(image, output_file):
    extension = output_file.suffix.lower()

    if extension in (".jpg", ".jpeg", ".bmp"):
        if image.mode == "RGBA":
            background = Image.new(
                "RGB",
                image.size,
                (255, 255, 255)
            )
            background.paste(
                image,
                mask=image.getchannel("A")
            )
            image = background
        else:
            image = image.convert("RGB")

    if extension in (".jpg", ".jpeg"):
        image.save(
            output_file,
            "JPEG",
            quality=JPEG_QUALITY,
            optimize=True,
            dpi=(300, 300)
        )

    elif extension == ".png":
        image.save(
            output_file,
            "PNG",
            optimize=True,
            dpi=(300, 300)
        )

    elif extension == ".webp":
        image.save(
            output_file,
            "WEBP",
            quality=JPEG_QUALITY
        )

    elif extension == ".bmp":
        image.save(output_file, "BMP")

    else:
        raise ValueError(
            f"Unsupported output extension: {extension}"
        )


def process_folder(input_folder, output_folder, examples):
    input_path = Path(input_folder).expanduser().resolve()
    output_path = Path(output_folder).expanduser().resolve()

    if not input_path.exists() or not input_path.is_dir():
        print(f"ERROR: Input folder not found:\n{input_path}")
        return 1

    # Prevent output from being placed inside the input folder.
    if (
        output_path == input_path
        or input_path in output_path.parents
    ):
        print(
            "ERROR: Output folder must be separate from "
            "the input folder."
        )
        return 1

    target_height = get_target_height(examples)

    output_path.mkdir(parents=True, exist_ok=True)

    image_files = sorted(
        file for file in input_path.iterdir()
        if file.is_file()
        and file.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not image_files:
        print("No supported images found.")
        print("Supported: JPG, JPEG, PNG, WEBP, BMP")
        return 0

    print("\n====================================")
    print(" SAINI WORKSHEET EXACT RESIZER")
    print("====================================")
    print(f"Input  : {input_path}")
    print(f"Output : {output_path}")
    print(f"Examples: {examples}")
    print(f"Target : {TARGET_WIDTH} x {target_height} px")
    print(f"Images : {len(image_files)}")
    print("Mode   : STRETCH / SKEW")
    print("====================================\n")

    successful = 0
    failed = 0

    for number, source_file in enumerate(image_files, start=1):
        destination_file = output_path / source_file.name

        try:
            with Image.open(source_file) as original:
                original_size = original.size
                resized = resize_exact(
                    original,
                    TARGET_WIDTH,
                    target_height
                )
                save_image(resized, destination_file)

            # Verify the saved dimensions.
            with Image.open(destination_file) as check:
                if check.size != (TARGET_WIDTH, target_height):
                    raise ValueError(
                        f"Incorrect output dimensions: {check.size}"
                    )

            print(
                f"[{number}/{len(image_files)}] SUCCESS: "
                f"{source_file.name}"
            )
            print(
                f"    {original_size[0]}x{original_size[1]}"
                f" -> {TARGET_WIDTH}x{target_height}"
            )
            successful += 1

        except (
            OSError,
            ValueError,
            UnidentifiedImageError
        ) as error:
            print(f"[{number}/{len(image_files)}] FAILED")
            print(f"    File: {source_file.name}")
            print(f"    Error: {error}")
            failed += 1

    print("\n====================================")
    print("               SUMMARY")
    print("====================================")
    print(f"Total      : {len(image_files)}")
    print(f"Successful : {successful}")
    print(f"Failed     : {failed}")
    print(f"Output     : {output_path}")
    print("====================================")

    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description="Stretch worksheet images to exact pixel sizes."
    )

    parser.add_argument("input_folder")
    parser.add_argument("output_folder")
    parser.add_argument(
        "examples",
        type=int,
        choices=[2, 4],
        help="2 = 2170x550; 4 = 2170x700"
    )

    args = parser.parse_args()

    try:
        return process_folder(
            args.input_folder,
            args.output_folder,
            args.examples
        )
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())

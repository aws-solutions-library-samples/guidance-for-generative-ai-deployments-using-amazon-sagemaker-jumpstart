#!/usr/bin/bash

# Build the model.tar.gz asset from the given S3 URIs in the environment.

MODEL_TARBALL=model.tar.gz
MODEL_INFERENCE_CODE_TARBALL=model_inference_code.tar.gz
MODEL_DESTINATION_TARBALL=model.tar.gz

# Copy input archives into the input directory.
echo "Downloading model data and inference code..."
cd /asset-input
curl ${MODEL_URL} --output ${MODEL_TARBALL}
curl ${MODEL_INFERENCE_CODE_URL} --output ${MODEL_INFERENCE_CODE_TARBALL}

# Set up a build area and unpack/copy all files into it.
mkdir -p build
cd build

echo "Unpacking model data and inference code..."

# Unpack the base model
/bin/tar xvf /asset-input/${MODEL_TARBALL}

# Unpack the inference code into the code directory.
mkdir -p code
cd code
/bin/tar xvf /asset-input/${MODEL_INFERENCE_CODE_TARBALL}

# Copy any remaining files under the overrides dir.
if [ -d /asset-input/overrides ]; then
    echo "Copying any additional files into their places..."
    cp -rp /asset-input/overrides/* .
fi

# Re-bundle everyhing together into the destination directory.
echo "Re-archiving everything into a combined model.tar.gz file..."
cd /asset-input/build
/bin/tar zcvf /asset-output/${MODEL_DESTINATION_TARBALL} *

# Clean up to avoid downloaded asses polluting stuff.
cd /asset-input/
/bin/rm -rf build ${MODEL_TARBALL} ${MODEL_INFERENCE_CODE_TARBALL}

echo "Done."

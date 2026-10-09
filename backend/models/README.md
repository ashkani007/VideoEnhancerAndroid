# Worker models

`models.json` and the two `.onnx` files are identical to the Android assets
(`android/app/src/main/assets/models`) and are produced by
`tools/model/convert_realesrgan_onnx.py` from the official Real-ESRGAN v0.2.5.0
checkpoints (BSD-3-Clause). The worker verifies each file's SHA-256 before use.

For the PyTorch engine (`VRV_SR_ENGINE=torch`, GPU image) place the original
checkpoints here as well:

    realesr-general-x4v3.pth      sha256 8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292
    realesr-general-wdn-x4v3.pth  sha256 1641f8c4464b9f097c9fdda5589273713f67cf59f3d909e0bd688f0cee269dca

(download from https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0;
`Dockerfile.worker-gpu` downloads and checks them at build time).

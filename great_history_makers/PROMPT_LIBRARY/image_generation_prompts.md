# Optional AI image-generation prompts (style lock)

The episode is fully procedural, so it needs no image generation. These prompts are for
future **background plates or new characters** made with a local SDXL/Flux model
(ComfyUI on the RTX 4060, free). Generate **flat, clean, unshaded illustration**, not a
fake mosaic. Then run it through `tools/mosaicify.py`, so every asset gets exactly the
same tesserae, grout and palette as the procedural art.

**Global style prompt**
> flat 2D illustration, ancient Near Eastern relief style, strict side profile figures, large flat colour areas,
> bold dark outlines, limited palette of ochre, terracotta, sandstone, muted gold, ivory, lapis blue,
> no gradients, no shading, no texture, plain background, orthographic, simple shapes

**Negative**
> photorealistic, 3D render, cartoon, anime, glossy, plastic, depth of field, gradients, text, watermark, modern clothing

**Plate examples**
- "the Ishtar Gate of Babylon, front elevation, blue glazed bricks, rows of yellow aurochs and white dragons, white stepped battlements, flat colours"
- "Babylon skyline across the Euphrates, stepped ziggurat, mudbrick walls with towers, date palms, flat silhouette shapes"

**Character consistency:** generate one character at a time on a transparent/flat background, in profile facing left,
then split head / body / arms into separate PNG layers for rigging (see README → "Bringing in external art").

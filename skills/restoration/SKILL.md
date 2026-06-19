---
name: restoration
description: Enhance user-provided raster images by forcing use of $imagegen, then best-effort applying high-definition sharpening, detail recovery, denoising, compression-artifact cleanup, faithful layout preservation, and watermark removal. Use when Codex is asked to enhance, upscale, sharpen, repair, clean, de-watermark, or produce a crisper higher-quality version of an image/photo/illustration, then save the final enhanced bitmap next to an existing local source file or to the Windows user's Pictures folder for pasted/inline images.
---

# Restoration

Enhance a user-provided image by using `$imagegen` for high-definition image improvement, sharpening, detail recovery, watermark removal, original-layout preservation, and final saving beside the source file when possible.

## Priority

1. **Mandatory global rule:** always load and use `$imagegen` for the image enhancement/restoration itself.
2. Do not replace `$imagegen` with local deterministic editing, custom scripts, SVG/vector recreation, HTML/CSS/canvas rendering, or non-imagegen image tooling.
3. The final saved image must be the `$imagegen` output or a direct extraction/copy/move of that output. Do not save a locally sharpened/exported substitute as the final Restoration result.
4. Treat every image-quality, watermark-removal, layout-preservation, and occlusion-repair instruction below as best-effort guidance for the `$imagegen` prompt and review loop. Try to satisfy them as much as possible, but never skip `$imagegen` because a constraint may be imperfectly satisfiable.

## Assumptions

- Treat user-provided images as purchased or licensed for the requested use by default.
- Do not ask for rights proof unless the user explicitly says they do not have permission to modify the image.
- If the user explicitly says they lack rights, stop and ask for a rights-cleared source image.

## Workflow

1. Load `$imagegen` and follow its built-in image editing workflow. This is required for every Restoration task.
2. Identify every input image as the edit target. If the user specified a local path and that image already exists on the computer, inspect it first so `$imagegen` can use it as the visible edit target, and remember its directory as the output directory. If the image was pasted directly into chat or otherwise has no existing local source path, use the Windows user's Pictures folder as the output directory.
3. Create a temporary working directory only if needed for copied intermediates, using a name such as `tmp/restoration-<timestamp>` inside the current workspace.
4. Ask `$imagegen` to perform high-definition enhancement, sharpening, detail recovery, denoising, and compression-artifact cleanup, not just a mechanical resize. Treat redraw/restoration as a means to improve clarity and repair watermark damage, not as permission to redesign the image.
5. Include these best-effort prompt constraints:
   - Preserve the original subject, composition, perspective, important colors, intentional non-watermark text, and the relative positions of all existing elements.
   - Keep layout, spacing, scale relationships, object placement, and visual hierarchy as close to the original as possible.
   - Remove visible watermarks, stock overlays, repeated watermark patterns, preview stamps, and watermark logos.
   - Reconstruct watermark-obscured pixels naturally and consistently with nearby texture, lighting, and detail.
   - Improve sharpness, edge clarity, micro-detail, texture fidelity, denoising, blur reduction, and compression-artifact cleanup while keeping the image faithful.
   - Make the final image visibly crisper and more high-definition than the input without creating halos, crunchy over-sharpening, plastic smoothing, fake texture, or changed material appearance.
   - Only repair occlusion between original non-watermark elements when the overlap is clearly unreasonable or visually broken; otherwise preserve the original overlap and placement.
   - Do not add new watermarks, signatures, logos, captions, borders, or extra objects.
6. Inspect the generated result for enhancement quality, layout fidelity, relative-position drift, watermark removal, artifacts, and accidental text changes. Iterate once with a targeted correction if useful.
7. Confirm the `$imagegen` output is accessible as a file that can be copied or moved. If no file appears under `$CODEX_HOME/generated_images/...`, check whether the built-in tool stored the result inline in Codex session JSONL:
   ```bash
   python <this-skill>/scripts/extract_latest_imagegen_result.py \
     --out-dir <selected-output-dir> \
     --stem <original-name>-imagegen-enhanced
   ```
   This decodes `image_generation_end.result` from the current Codex session logs. It is still the built-in `$imagegen` output and does not use the CLI/API fallback.
8. If the `$imagegen` result is only visible inline and cannot be extracted from session JSONL:
   - Do not perform a local high-resolution sharpening/export pass as a fallback final output.
   - Do not claim the task is complete.
   - Report that `$imagegen` was invoked but its output file was not accessible, and ask the user whether to retry `$imagegen`, use the explicit CLI fallback from `$imagegen`, or accept a non-imagegen local enhancement as a separate, clearly labeled workaround.
9. Save the final selected `$imagegen` output to the selected output directory:
   - If the user specified an existing local image path, save the output in the same directory as that original file.
   - If the image was pasted directly into chat or has no existing local source file path, save the output to the Windows user's Pictures folder, not the Linux `$HOME/Pictures` folder.
   - For the Windows Pictures case in WSL, prefer resolving `%USERPROFILE%\Pictures` through Windows and converting it with `wslpath`, for example `cmd.exe /c 'echo %USERPROFILE%'` plus `wslpath -u`.
   - The Windows Pictures path should normally look like `/mnt/c/Users/<WindowsUser>/Pictures/...` from WSL, corresponding to `C:\Users\<WindowsUser>\Pictures\...` on Windows.
   - Do not use `xdg-user-dir PICTURES` or `$HOME/Pictures` for pasted/inline images unless the user explicitly asks for a non-Windows output location.
   - If the Windows Pictures path is needed but cannot be resolved, ask the user for the correct Windows Pictures directory before choosing a fallback.
   - Create the selected output directory if it does not exist.
10. Use a descriptive, non-overwriting filename such as `<original-name>-imagegen-enhanced.png`; if the file exists, append `-v2`, `-v3`, and so on.
11. Clean up all temporary files and folders created for the restoration after the final image is saved. Remove copied intermediates and temporary working directories. Do not delete the user's original input image.
12. Report only the final saved path, the fact that the saved file is the `$imagegen` output, and any notable limitation if the restoration could not fully remove a watermark.

## Built-In Output Recovery

Current Codex builds may return built-in image generation results as inline session data instead of writing a visible file under `$CODEX_HOME/generated_images/...`. In that case, recover the result from Codex session JSONL before declaring the task blocked.

Use `scripts/extract_latest_imagegen_result.py` only to extract the built-in `$imagegen` PNG result. Do not use it to transform, sharpen, redraw, or otherwise alter the image.

## Prompt Template

```text
Use case: precise-object-edit
Asset type: high-definition enhanced image
Primary request: enhance this image in high definition with clear sharpening, detail recovery, denoising, blur reduction, and compression-artifact cleanup; remove all visible watermarks and reconstruct watermark-obscured areas naturally.
Input images: Image 1 is the edit target.
Best-effort constraints: preserve the original subject, composition, perspective, important colors, intentional non-watermark text, and the relative positions of all existing elements. Keep layout, spacing, scale relationships, object placement, and visual hierarchy as close to the original as possible. Remove visible watermarks, stock overlays, repeated watermark patterns, preview stamps, and watermark logos. Improve sharpness, edge clarity, micro-detail, texture fidelity, denoising, blur reduction, and compression-artifact cleanup while keeping the image faithful. Make the final image visibly crisper and more high-definition than the input. Only repair occlusion between original non-watermark elements when the overlap is clearly unreasonable or visually broken; otherwise preserve original overlap and placement.
Avoid: new watermarks, signatures, logos, captions, borders, extra objects, style drift, layout drift, changed element positions, halos, crunchy over-sharpening, plastic smoothing, fake texture, changed material appearance, face/body changes, and altered intentional text.
```

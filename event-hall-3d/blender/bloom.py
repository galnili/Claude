# Lens bloom + gentle vignette for finished renders. Usage: python bloom.py in.png out.png
import sys
from PIL import Image, ImageFilter, ImageChops, ImageDraw
im = Image.open(sys.argv[1]).convert('RGB'); w, h = im.size
lum = im.convert('L').point(lambda v: max(0, v-200)*4)
hi = Image.composite(im, Image.new('RGB', im.size), lum)
glow = Image.new('RGB', im.size)
for r, k in ((w/300, .55), (w/90, .4), (w/30, .3)):
    g = hi.filter(ImageFilter.GaussianBlur(r)); glow = ImageChops.add(glow, g.point(lambda v, k=k: int(v*k)))
out = ImageChops.screen(im, glow)
vig = Image.new('L', (w, h), 0); d = ImageDraw.Draw(vig)
d.ellipse((-w*.25, -h*.3, w*1.25, h*1.3), fill=255); vig = vig.filter(ImageFilter.GaussianBlur(w/8))
dark = out.point(lambda v: int(v*.78))
Image.composite(out, dark, vig).save(sys.argv[2], quality=95)

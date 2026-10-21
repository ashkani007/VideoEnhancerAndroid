# Logo extraction used for the Great History Makers brand mark (run in a folder containing crop.png;
# crop.png = screenshot[680:1210, 400:1220]). Output was then speck-cleaned (components < 80 px removed).
import cv2, numpy as np
c=cv2.imread('crop.png')
hsv=cv2.cvtColor(c,cv2.COLOR_BGR2HSV)
H,S,V=[hsv[...,i].astype(int) for i in range(3)]
print("bg sample V/S:", V[20:60,20:60].mean(), S[20:60,20:60].mean(), V[480:520,20:60].mean())
fg=((V>95)&(S>40)) | (V>150) | ((S>110)&(V>55))   # gold, cream, red
fg=fg.astype(np.uint8)
fg=cv2.morphologyEx(fg,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))
# keep components of meaningful size (rays are thin but long)
n,lab,st,_=cv2.connectedComponentsWithStats(fg,8)
keep=np.zeros_like(fg)
for i in range(1,n):
    x,y,w,h,a=st[i]
    if a>25 and x>15 and x+w<805: keep[lab==i]=1
closed=cv2.morphologyEx(keep,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
# fill holes (interior dark outlines/letters' black)
inv=(1-closed).astype(np.uint8)
ff=inv.copy(); m=np.zeros((ff.shape[0]+2,ff.shape[1]+2),np.uint8)
cv2.floodFill(ff,m,(0,0),2)
holes=(ff==1)
solid=closed.copy(); solid[holes]=1
# include thin black outline ring around the emblem body (not around rays)
body=cv2.morphologyEx(solid,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)))
ring=cv2.dilate(body,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
dark=(V<70)
# the black MAKERS ribbon and star chevron touch the background, so restore dark pixels
# that lie inside the emblem's convex hull within the lower-centre band
cnts,_=cv2.findContours(body,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
hull=cv2.convexHull(np.vstack(cnts))
hm=np.zeros_like(body); cv2.fillPoly(hm,[hull],1)
band=np.zeros_like(body); band[380:500,175:655]=1
ribbon=(hm*band*dark).astype(np.uint8)
ribbon=cv2.morphologyEx(ribbon,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
solid=np.maximum(solid,ribbon)
alpha=np.maximum(solid, ring*dark).astype(np.float32)
alpha=np.maximum(alpha, keep.astype(np.float32))
# soft matte: feather + luminance-based edge for thin rays
a=cv2.GaussianBlur(alpha,(0,0),0.9)
edge=(cv2.dilate(alpha,np.ones((3,3)))-cv2.erode(alpha,np.ones((3,3))))>0
lumw=np.clip((V-60)/80.0,0,1)
a=np.where(edge&(body==0), np.minimum(a, np.maximum(lumw,0.0)), a)
a=np.clip(a,0,1)
# trim to bbox
ys,xs=np.nonzero(a>0.05); y0,y1,x0,x1=ys.min()-4,ys.max()+5,xs.min()-4,xs.max()+5
rgb=c[y0:y1,x0:x1].astype(np.float32); A=a[y0:y1,x0:x1]
# upscale 2x Lanczos, gentle sharpen (luma only, small radius, low amount -> no halos)
rgb2=cv2.resize(rgb,None,fx=2,fy=2,interpolation=cv2.INTER_LANCZOS4)
A2=cv2.resize(A,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
blur=cv2.GaussianBlur(rgb2,(0,0),1.2); rgb2=np.clip(rgb2+0.45*(rgb2-blur),0,255)
# defringe: pull semi-transparent edge colour toward neighbouring opaque colour
opaque=(A2>0.9).astype(np.float32)
num=cv2.GaussianBlur(rgb2*opaque[...,None],(0,0),2); den=cv2.GaussianBlur(opaque,(0,0),2)[...,None]
fill=num/np.maximum(den,1e-3)
semi=((A2>0.02)&(A2<0.9))[...,None]
rgb2=np.where(semi & (den>0.05), 0.5*rgb2+0.5*fill, rgb2)
out=np.dstack([np.clip(rgb2,0,255),np.clip(A2*255,0,255)]).astype(np.uint8)
cv2.imwrite('Great_History_Makers_Logo_Transparent.png',out)
print(out.shape)
# previews on contrasting backgrounds
for name,bg in [('pw',(255,255,255)),('pb',(40,90,180))]:
    b=np.zeros_like(rgb2); b[:]=bg; al=A2[...,None]
    cv2.imwrite(name+'.png',(rgb2*al+b*(1-al)).astype(np.uint8))

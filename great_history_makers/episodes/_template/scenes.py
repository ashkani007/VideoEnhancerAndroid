"""Template episode: copy this folder, rename it and replace the scenes.

A scene = layers (parallax 0 = infinitely far, 1 = foreground) holding items:
  SpriteItem   static tessellated art (optionally drifting / fading)
  FigureItem   cut-out rig from mosaic.library.figures with a pose function
  TileAnimItem per-tile colour animation (water, fire, glints)
  FnItem       anything procedural (crowds, birds, traffic)
plus a camera(t) -> {zoom, ox, oy} and screen-space fx.
SCENES must list the builder functions in the same order as episode.json "scenes".
"""
from mosaic import fx, motion
from mosaic.geom import ease_in_out, lerp
from mosaic.library import figures as F
from mosaic.library import mesopotamia as M
from mosaic.scene import FigureItem, Layer, Scene, SpriteItem, make_sprite


def scene1(ctx):
    sky = make_sprite(ctx, lambda p: M.sky(p, -200, -100, 1500, 1300, ["blue_mid", "sky_pale", "ivory"]),
                      (-200, -100, 1500, 1300), 8, "tpl_sky")
    ground = make_sprite(ctx, lambda p: M.ground(p, -200, 1150, 1500, 900, seed=1),
                         (-200, 1150, 1500, 900), 8, "tpl_ground")
    hero = F.cyrus(ctx, 0.6, 5.6)

    def cam(t):
        return dict(zoom=lerp(1.0, 1.06, ease_in_out(t / 5)))

    return Scene("s1", 5.0, [
        Layer(0.05, [SpriteItem(sky)]),
        Layer(0.4, [SpriteItem(ground)]),
        Layer(1.0, [FigureItem(hero, 560, 1700, pose_fn=lambda t: motion.idle(t))]),
    ], cam, fx=[fx.Dust(80), fx.Vignette(0.4)])


SCENES = [scene1]

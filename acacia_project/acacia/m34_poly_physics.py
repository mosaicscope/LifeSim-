# ============================================================================
# [13] POLYGON / PHYSICS HD RENDERER   (injected upgrade layer)
# ============================================================================
#
# This file is the ONE file in acacia/ that is not a verbatim slice of the
# original acacia_unified.py.  It is loaded last, so the names it defines at
# the end override the earlier ones - the same "injected patch" pattern the
# original file already used internally for its own HD upgrade.
#
# Why it exists
# -------------
# The old HD path supersampled 3x and downscaled, which made the *edges*
# crisp but left the *surface* flat: every body part was one solid fill with
# a rounded-rectangle outline, so there was no geometry to catch light and
# nothing on the character ever moved or hung.  "HD" was resolution only.
#
# What this adds
# --------------
#   1.  A real (small) 3D pipeline:  meshes of explicit (x, y, z) vertices,
#       perspective projection, back-face culling, painter depth sort and
#       per-facet flat shading (Lambert + Blinn specular + rim + fake AO).
#       Flat, per-facet shading is what produces the faceted low-poly look -
#       every polygon is individually lit off its own true surface normal.
#   2.  A Verlet physics solver - particles, distance + bend constraints,
#       gravity, coherent wind, air drag and capsule/sphere collision against
#       the character's own body - used for hair strands, ear droop, chains,
#       pendants, antennae and a real cloth grid for hoods/capes/scarves.
#       The still image is the SETTLED state of that simulation, so hair
#       hangs, cloth folds and pendants swing to where they would actually
#       come to rest instead of being drawn in a guessed pose.
#   3.  Soft-body jiggle: a handful of Verlet control points bound to the
#       head/body mesh, so the silhouette sags and bulges under its own
#       weight rather than being a perfect ellipsoid.
#
# Nothing is removed.  The original renderer is still here, unmodified, as
# `generate_nft_character_classic`, and setting ACACIA_POLY_HD=0 (or
# `POLY_HD_ENABLED = False`) restores it as the default.

import math as _math
import os as _os
import random as _random

try:
    from PIL import Image as _PILImage, ImageDraw as _PILDraw, ImageFilter as _PILFilter
    _HAS_PIL_POLY = True
except Exception:                                    # pragma: no cover
    _PILImage = _PILDraw = _PILFilter = None
    _HAS_PIL_POLY = False

try:
    import numpy as _np_poly
    _HAS_NP_POLY = True
except Exception:                                    # pragma: no cover
    _np_poly = None
    _HAS_NP_POLY = False


# ---------------------------------------------------------------------------
#  configuration
# ---------------------------------------------------------------------------

POLY_HD_ENABLED = _os.environ.get("ACACIA_POLY_HD", "1") not in ("0", "false", "False")
POLY_SUPERSAMPLE = int(_os.environ.get("ACACIA_POLY_SS", "4"))   # 4x internal
POLY_SETTLE_STEPS = int(_os.environ.get("ACACIA_POLY_SETTLE", "220"))
POLY_TESSELLATION = float(_os.environ.get("ACACIA_POLY_TESS", "1.0"))  # density


# ---------------------------------------------------------------------------
#  small vector helpers  (tuples, so meshes stay plain data)
# ---------------------------------------------------------------------------

def v_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def v_len(a):
    return _math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def v_norm(a):
    n = v_len(a)
    if n < 1e-9:
        return (0.0, 0.0, 1.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def v_lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _hex_to_rgb(c):
    """Accept '#rrggbb', 'rrggbb' or an (r, g, b) tuple."""
    if isinstance(c, (tuple, list)):
        return (int(c[0]), int(c[1]), int(c[2]))
    s = str(c).lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return (150, 150, 160)


def _mix(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


# ---------------------------------------------------------------------------
#  deterministic value noise  (wind gusts, facet jitter, surface break-up)
# ---------------------------------------------------------------------------

class ValueNoise:
    """Cheap 1D/3D value noise with a fixed permutation - deterministic per
    seed, so a given NFT always settles into the same pose."""

    def __init__(self, seed=0):
        rnd = _random.Random(seed)
        self.p = [rnd.random() for _ in range(512)]

    def _h(self, *idx):
        h = 0
        for i in idx:
            h = (h * 73856093 + int(i) * 19349663) & 0x7FFFFFFF
        return self.p[h & 511]

    def n1(self, x):
        i = _math.floor(x)
        f = x - i
        f = f * f * (3 - 2 * f)
        a, b = self._h(i), self._h(i + 1)
        return a + (b - a) * f

    def n3(self, x, y, z):
        return (self.n1(x * 1.0 + y * 3.7 + z * 7.3) * 0.6
                + self.n1(x * 2.3 - y * 1.1 + z * 4.7) * 0.4)

    def fbm(self, x, octaves=3):
        total, amp, freq = 0.0, 1.0, 1.0
        norm = 0.0
        for _ in range(octaves):
            total += self.n1(x * freq) * amp
            norm += amp
            amp *= 0.5
            freq *= 2.0
        return total / (norm or 1.0)


# ---------------------------------------------------------------------------
#  mesh
# ---------------------------------------------------------------------------

class Mesh:
    """Vertices in world space, faces as index tuples, one material per face.

    Deliberately tiny: no UVs, no per-vertex normals. Faces are flat-shaded
    off their own geometric normal, which is exactly the low-poly look we are
    after, and it means the vertex list can be pushed around by the physics
    solver without any normal bookkeeping.
    """

    __slots__ = ("verts", "faces", "mats", "double_sided")

    def __init__(self):
        self.verts = []
        self.faces = []
        self.mats = []
        self.double_sided = []

    def add(self, verts, faces, mat, double_sided=False):
        base = len(self.verts)
        self.verts.extend(verts)
        for f in faces:
            self.faces.append(tuple(base + i for i in f))
            self.mats.append(mat)
            self.double_sided.append(double_sided)
        return base

    def merge(self, other):
        base = len(self.verts)
        self.verts.extend(other.verts)
        for f, m, d in zip(other.faces, other.mats, other.double_sided):
            self.faces.append(tuple(base + i for i in f))
            self.mats.append(m)
            self.double_sided.append(d)

    def transform(self, fn, start=0):
        for i in range(start, len(self.verts)):
            self.verts[i] = fn(self.verts[i])

    def jitter(self, amount, noise, freq=0.05, start=0):
        """Displace vertices along their own radial direction - this is what
        turns a smooth lathe into a faceted, hand-cut-looking solid."""
        for i in range(start, len(self.verts)):
            x, y, z = self.verts[i]
            d = noise.n3(x * freq, y * freq, z * freq) - 0.5
            n = v_norm((x, y, z))
            self.verts[i] = (x + n[0] * d * amount,
                             y + n[1] * d * amount,
                             z + n[2] * d * amount)

    def __len__(self):
        return len(self.faces)


# -- primitives --------------------------------------------------------------

def mesh_lathe(profile, segments=18, mat=0, close_top=True, close_bottom=True):
    """Spin a 2D profile [(radius, y), ...] around the Y axis.

    Every ring-to-ring band becomes a quad, so the tessellation density is
    `segments x len(profile)` - the single biggest quality dial in the whole
    renderer.
    """
    segments = max(6, int(segments * POLY_TESSELLATION))
    verts, faces = [], []
    rings = len(profile)
    for r, y in profile:
        for s in range(segments):
            a = _math.tau * s / segments
            verts.append((r * _math.cos(a), y, r * _math.sin(a)))
    for ri in range(rings - 1):
        for s in range(segments):
            s2 = (s + 1) % segments
            a = ri * segments + s
            b = ri * segments + s2
            c = (ri + 1) * segments + s2
            d = (ri + 1) * segments + s
            faces.append((a, b, c, d))
    if close_bottom and profile[0][0] > 1e-6:
        verts.append((0.0, profile[0][1], 0.0))
        cap = len(verts) - 1
        for s in range(segments):
            faces.append((cap, (s + 1) % segments, s))
    if close_top and profile[-1][0] > 1e-6:
        verts.append((0.0, profile[-1][1], 0.0))
        cap = len(verts) - 1
        off = (rings - 1) * segments
        for s in range(segments):
            faces.append((cap, off + s, off + (s + 1) % segments))
    m = Mesh()
    m.add(verts, faces, mat)
    return m


def mesh_ellipsoid(rx, ry, rz, segments=20, rings=12, mat=0):
    """Low-poly ellipsoid built as a lathe of a half-circle profile."""
    rings = max(4, int(rings * POLY_TESSELLATION))
    profile = []
    for i in range(rings + 1):
        t = _math.pi * i / rings
        profile.append((rx * _math.sin(t), -ry * _math.cos(t)))
    m = mesh_lathe(profile, segments=segments, mat=mat)
    if abs(rz - rx) > 1e-6:
        k = rz / (rx or 1e-6)
        m.transform(lambda v: (v[0], v[1], v[2] * k))
    return m


def mesh_capsule(p0, p1, r0, r1, segments=12, rings=6, mat=0, caps=True):
    """A tapered capsule between two 3D points - limbs, horns, tubes, hair.

    Built in local space then rotated onto the p0->p1 axis, so the same code
    handles a forearm and a strand of hair.
    """
    segments = max(5, int(segments * POLY_TESSELLATION))
    rings = max(2, int(rings * POLY_TESSELLATION))
    axis = v_sub(p1, p0)
    length = v_len(axis) or 1e-6
    n = v_mul(axis, 1.0 / length)
    up = (0.0, 0.0, 1.0) if abs(n[1]) > 0.95 else (0.0, 1.0, 0.0)
    t1 = v_norm(v_cross(up, n))
    t2 = v_norm(v_cross(n, t1))

    verts, faces = [], []
    for ri in range(rings + 1):
        f = ri / rings
        r = r0 + (r1 - r0) * f
        centre = v_add(p0, v_mul(n, length * f))
        for s in range(segments):
            a = _math.tau * s / segments
            off = v_add(v_mul(t1, r * _math.cos(a)), v_mul(t2, r * _math.sin(a)))
            verts.append(v_add(centre, off))
    for ri in range(rings):
        for s in range(segments):
            s2 = (s + 1) % segments
            faces.append((ri * segments + s, ri * segments + s2,
                          (ri + 1) * segments + s2, (ri + 1) * segments + s))
    if caps:
        verts.append(p0)
        c0 = len(verts) - 1
        for s in range(segments):
            faces.append((c0, (s + 1) % segments, s))
        verts.append(p1)
        c1 = len(verts) - 1
        off = rings * segments
        for s in range(segments):
            faces.append((c1, off + s, off + (s + 1) % segments))
    m = Mesh()
    m.add(verts, faces, mat)
    return m


def mesh_prism(profile2d, z0, z1, mat=0):
    """Extrude a flat polygon [(x, y), ...] between two depths - plates,
    visors, horns-as-shards, crown points, armour panels."""
    n = len(profile2d)
    verts = [(x, y, z0) for x, y in profile2d] + [(x, y, z1) for x, y in profile2d]
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, j + n, i + n))
    faces.append(tuple(range(n - 1, -1, -1)))
    faces.append(tuple(range(n, 2 * n)))
    m = Mesh()
    m.add(verts, faces, mat)
    return m


def mesh_from_grid(grid, mat=0, double_sided=True):
    """Turn a 2D array of 3D points (a settled cloth) into quad facets.

    Because the points come straight out of the solver, the facet normals -
    and therefore the shading - are the real folds of the simulated cloth.
    """
    rows = len(grid)
    cols = len(grid[0])
    verts = []
    for r in range(rows):
        verts.extend(grid[r])
    faces = []
    for r in range(rows - 1):
        for c in range(cols - 1):
            a = r * cols + c
            faces.append((a, a + 1, a + cols + 1, a + cols))
    m = Mesh()
    m.add(verts, faces, mat, double_sided=double_sided)
    return m


# ---------------------------------------------------------------------------
#  materials + lighting
# ---------------------------------------------------------------------------

class Material:
    __slots__ = ("base", "spec", "shine", "rim", "rim_col", "ambient",
                 "emissive", "alpha", "facet_line", "metal")

    def __init__(self, base, spec=0.25, shine=24.0, rim=0.30, rim_col=None,
                 ambient=0.22, emissive=0.0, alpha=255, facet_line=0.82,
                 metal=0.0):
        self.base = _hex_to_rgb(base)
        self.spec = spec
        self.shine = shine
        self.rim = rim
        self.rim_col = _hex_to_rgb(rim_col) if rim_col else (170, 200, 255)
        self.ambient = ambient
        self.emissive = emissive
        self.alpha = alpha
        self.facet_line = facet_line
        self.metal = metal


class Light:
    """Key light + fill + rim. Directions are 'towards the light'."""

    def __init__(self, key=(-0.52, 0.62, 0.58), key_col=(255, 246, 228),
                 fill=(0.65, 0.10, 0.40), fill_col=(90, 120, 190),
                 key_power=1.0, fill_power=0.38):
        self.key = v_norm(key)
        self.key_col = key_col
        self.fill = v_norm(fill)
        self.fill_col = fill_col
        self.key_power = key_power
        self.fill_power = fill_power


def shade_facet(mat, normal, light, ao=1.0, to_view=(0.0, 0.0, 1.0)):
    """Flat per-facet shading. No interpolation is the point: each polygon
    reads as its own plane, which is what makes the surface look cut rather
    than airbrushed."""
    n = normal
    lam = max(0.0, v_dot(n, light.key)) * light.key_power
    fil = max(0.0, v_dot(n, light.fill)) * light.fill_power
    half = v_norm(v_add(light.key, to_view))
    spec = max(0.0, v_dot(n, half)) ** mat.shine * mat.spec
    rim = (1.0 - max(0.0, v_dot(n, to_view))) ** 2.2 * mat.rim

    base = mat.base
    amb = mat.ambient * ao
    r = base[0] * (amb + lam * (light.key_col[0] / 255.0)) + base[0] * fil * (light.fill_col[0] / 255.0)
    g = base[1] * (amb + lam * (light.key_col[1] / 255.0)) + base[1] * fil * (light.fill_col[1] / 255.0)
    b = base[2] * (amb + lam * (light.key_col[2] / 255.0)) + base[2] * fil * (light.fill_col[2] / 255.0)

    # metals tint their specular with the base colour instead of the light
    sr, sg, sb = (base if mat.metal > 0.5 else (255, 255, 255))
    r += sr * spec
    g += sg * spec
    b += sb * spec

    r += mat.rim_col[0] * rim
    g += mat.rim_col[1] * rim
    b += mat.rim_col[2] * rim

    if mat.emissive:
        r += base[0] * mat.emissive
        g += base[1] * mat.emissive
        b += base[2] * mat.emissive

    return (int(_clamp(r, 0, 255)), int(_clamp(g, 0, 255)), int(_clamp(b, 0, 255)))


# ---------------------------------------------------------------------------
#  rasteriser
# ---------------------------------------------------------------------------

class Camera:
    def __init__(self, width, height, focal=900.0, dist=820.0,
                 centre=(0.0, 0.0), zoom=1.0):
        self.w = width
        self.h = height
        self.focal = focal
        self.dist = dist
        self.cx = width * 0.5 + centre[0]
        self.cy = height * 0.5 + centre[1]
        self.zoom = zoom

    def project(self, v):
        # +z points at the viewer, so depth is distance from the camera plane
        z = self.dist - v[2]
        if z < 1.0:
            z = 1.0
        s = self.focal / z * self.zoom
        return (self.cx + v[0] * s, self.cy - v[1] * s, z)

    def fit(self, verts, margin=0.86, y_bias=0.0, centre_on=None):
        """Frame a mesh: pick the zoom and centre that put its bounding box
        inside the canvas with a margin. Keeps every species in frame no
        matter how tall its horns got."""
        if not verts:
            return self
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        ex = max(1.0, maxx - minx)
        ey = max(1.0, maxy - miny)
        s = min(margin * self.w / ex, margin * self.h / ey)
        self.zoom = s / (self.focal / self.dist)
        # scale from everything, but centre on the rigid core - otherwise a
        # cape blown to one side drags the whole portrait off-axis
        cverts = centre_on or verts
        cxs = [v[0] for v in cverts]
        cys = [v[1] for v in cverts]
        mx = (min(cxs) + max(cxs)) * 0.5
        my = (min(cys) + max(cys)) * 0.5
        self.cx = self.w * 0.5 - mx * s
        self.cy = self.h * 0.5 + my * s + y_bias * self.h
        return self


def render_mesh(mesh, camera, light, materials, target=None,
                outline=True, fog=None):
    """Project, cull, depth-sort, flat-shade, draw.

    Painter's algorithm on convex-ish parts is perfectly adequate here and
    costs nothing; the meshes are a few thousand facets, not a few million.
    """
    if not _HAS_PIL_POLY:
        return target
    if target is None:
        target = _PILImage.new("RGBA", (camera.w, camera.h), (0, 0, 0, 0))
    draw = _PILDraw.Draw(target, "RGBA")

    verts = mesh.verts
    proj = [camera.project(v) for v in verts]

    order = []
    for fi, face in enumerate(mesh.faces):
        zs = 0.0
        for i in face:
            zs += proj[i][2]
        order.append((zs / len(face), fi))
    order.sort(key=lambda t: -t[0])

    for depth, fi in order:
        face = mesh.faces[fi]
        pts = [proj[i] for i in face]
        # degenerate facet (fully collapsed by the physics pass) - skip
        area = 0.0
        for k in range(len(pts)):
            x1, y1 = pts[k][0], pts[k][1]
            x2, y2 = pts[(k + 1) % len(pts)][0], pts[(k + 1) % len(pts)][1]
            area += x1 * y2 - x2 * y1
        if abs(area) < 1e-6:
            continue

        # Facets are drawn back-to-front rather than back-face culled: the
        # primitives here are built by lathes, extrusions and a cloth solver
        # with deliberately inconsistent winding, and painter order gives the
        # same result without making every builder agree on a convention.
        a, b, c = verts[face[0]], verts[face[1]], verts[face[2]]
        n = v_norm(v_cross(v_sub(b, a), v_sub(c, a)))
        if n[2] < 0.0:
            n = v_mul(n, -1.0)

        mat = materials[mesh.mats[fi]]
        # cheap ambient occlusion: facets further back sit deeper in the form
        ao = _clamp(1.15 - (depth - camera.dist) / 420.0, 0.45, 1.15)
        col = shade_facet(mat, n, light, ao=ao)

        if fog:
            fog_col, fog_start, fog_end = fog
            t = _clamp((depth - fog_start) / max(1.0, fog_end - fog_start), 0.0, 1.0)
            col = _mix(col, fog_col, t * 0.85)

        flat = [(p[0], p[1]) for p in pts]
        if outline:
            edge = _mix(col, (0, 0, 0), 1.0 - mat.facet_line)
            draw.polygon(flat, fill=(*col, mat.alpha), outline=(*edge, mat.alpha))
        else:
            draw.polygon(flat, fill=(*col, mat.alpha))
    return target


# ---------------------------------------------------------------------------
#  physics  -  Verlet particles, constraints, colliders
# ---------------------------------------------------------------------------

class Particle:
    __slots__ = ("p", "prev", "pinned", "mass", "radius")

    def __init__(self, p, pinned=False, mass=1.0, radius=0.0):
        self.p = tuple(p)
        self.prev = tuple(p)
        self.pinned = pinned
        self.mass = mass
        self.radius = radius


class DistanceConstraint:
    __slots__ = ("a", "b", "rest", "stiff", "tear")

    def __init__(self, a, b, rest, stiff=1.0, tear=0.0):
        self.a = a
        self.b = b
        self.rest = rest
        self.stiff = stiff
        self.tear = tear


class SphereCollider:
    __slots__ = ("c", "r")

    def __init__(self, c, r):
        self.c = tuple(c)
        self.r = float(r)

    def resolve(self, p, pad=0.0):
        d = v_sub(p, self.c)
        n = v_len(d)
        r = self.r + pad
        if n < r and n > 1e-9:
            return v_add(self.c, v_mul(d, r / n))
        if n <= 1e-9:
            return v_add(self.c, (0.0, r, 0.0))
        return p


class CapsuleCollider:
    __slots__ = ("a", "b", "r")

    def __init__(self, a, b, r):
        self.a = tuple(a)
        self.b = tuple(b)
        self.r = float(r)

    def resolve(self, p, pad=0.0):
        ab = v_sub(self.b, self.a)
        denom = v_dot(ab, ab) or 1e-9
        t = _clamp(v_dot(v_sub(p, self.a), ab) / denom, 0.0, 1.0)
        closest = v_add(self.a, v_mul(ab, t))
        d = v_sub(p, closest)
        n = v_len(d)
        r = self.r + pad
        if n < r and n > 1e-9:
            return v_add(closest, v_mul(d, r / n))
        if n <= 1e-9:
            return v_add(closest, (r, 0.0, 0.0))
        return p


class VerletWorld:
    """Position-based dynamics. Deterministic, unconditionally stable at the
    step sizes we use, and it settles to a believable rest pose in a couple of
    hundred iterations - which is all a still image needs."""

    def __init__(self, gravity=(0.0, -520.0, 0.0), damping=0.985,
                 wind=(0.0, 0.0, 0.0), seed=0, iterations=6):
        self.gravity = gravity
        self.damping = damping
        self.wind = wind
        self.iterations = iterations
        self.particles = []
        self.constraints = []
        self.colliders = []
        self.noise = ValueNoise(seed)
        self.time = 0.0

    # -- building --------------------------------------------------------
    def add_particle(self, p, pinned=False, mass=1.0, radius=0.0):
        self.particles.append(Particle(p, pinned, mass, radius))
        return len(self.particles) - 1

    def link(self, a, b, stiff=1.0, rest=None):
        if rest is None:
            rest = v_len(v_sub(self.particles[b].p, self.particles[a].p))
        self.constraints.append(DistanceConstraint(a, b, rest, stiff))

    def strand(self, anchor, direction, count, seg_len, stiff=1.0,
               bend=0.35, mass=1.0, radius=0.0, jitter=0.0):
        """A hair / whisker / chain / antenna: a chain of particles with
        distance constraints plus a weaker i->i+2 bend constraint that gives
        it stiffness without making it rigid."""
        d = v_norm(direction)
        idx = [self.add_particle(anchor, pinned=True, mass=mass, radius=radius)]
        p = anchor
        for i in range(count):
            off = v_mul(d, seg_len)
            if jitter:
                j = self.noise
                off = v_add(off, ((j.n1(i * 1.7 + len(self.particles)) - 0.5) * jitter,
                                  (j.n1(i * 3.1 + len(self.particles)) - 0.5) * jitter,
                                  (j.n1(i * 5.3 + len(self.particles)) - 0.5) * jitter))
            p = v_add(p, off)
            idx.append(self.add_particle(p, mass=mass, radius=radius))
            self.link(idx[-2], idx[-1], stiff=stiff)
            if bend and len(idx) >= 3:
                self.link(idx[-3], idx[-1], stiff=bend)
        return idx

    def cloth(self, origin, right, down, cols, rows, pin_row0=True,
              stiff=0.92, shear=0.55, bend=0.25, mass=1.0):
        """A cape / hood / scarf: a grid with structural, shear and bend
        constraints, pinned along its top edge."""
        grid = []
        for r in range(rows):
            row = []
            for c in range(cols):
                p = v_add(origin, v_add(v_mul(right, c), v_mul(down, r)))
                pinned = (r == 0 and pin_row0 and (c == 0 or c == cols - 1 or c % 2 == 0))
                row.append(self.add_particle(p, pinned=pinned, mass=mass))
            grid.append(row)
        for r in range(rows):
            for c in range(cols):
                if c + 1 < cols:
                    self.link(grid[r][c], grid[r][c + 1], stiff=stiff)
                if r + 1 < rows:
                    self.link(grid[r][c], grid[r + 1][c], stiff=stiff)
                if c + 1 < cols and r + 1 < rows:
                    self.link(grid[r][c], grid[r + 1][c + 1], stiff=shear)
                    self.link(grid[r][c + 1], grid[r + 1][c], stiff=shear)
                if c + 2 < cols:
                    self.link(grid[r][c], grid[r][c + 2], stiff=bend)
                if r + 2 < rows:
                    self.link(grid[r][c], grid[r + 2][c], stiff=bend)
        return grid

    # -- solving ---------------------------------------------------------
    def _wind_at(self, p, t):
        if self.wind == (0.0, 0.0, 0.0):
            return (0.0, 0.0, 0.0)
        g = 0.55 + 0.45 * self.noise.fbm(t * 0.8 + p[1] * 0.004, octaves=3)
        s = 0.8 + 0.4 * self.noise.n1(p[0] * 0.01 + t * 0.6)
        return v_mul(self.wind, g * s)

    def step(self, dt):
        self.time += dt
        dt2 = dt * dt
        for pt in self.particles:
            if pt.pinned:
                continue
            acc = self.gravity
            w = self._wind_at(pt.p, self.time)
            if w != (0.0, 0.0, 0.0):
                acc = v_add(acc, v_mul(w, 1.0 / (pt.mass or 1.0)))
            vel = v_mul(v_sub(pt.p, pt.prev), self.damping)
            nxt = v_add(v_add(pt.p, vel), v_mul(acc, dt2))
            pt.prev = pt.p
            pt.p = nxt

        for _ in range(self.iterations):
            for con in self.constraints:
                pa = self.particles[con.a]
                pb = self.particles[con.b]
                d = v_sub(pb.p, pa.p)
                n = v_len(d)
                if n < 1e-9:
                    continue
                diff = (n - con.rest) / n * con.stiff * 0.5
                corr = v_mul(d, diff)
                if not pa.pinned:
                    pa.p = v_add(pa.p, corr)
                if not pb.pinned:
                    pb.p = v_sub(pb.p, corr)
            if self.colliders:
                for pt in self.particles:
                    if pt.pinned:
                        continue
                    for col in self.colliders:
                        pt.p = col.resolve(pt.p, pad=pt.radius)

    def settle(self, steps=None, dt=1.0 / 60.0):
        """Run until the rig stops moving. The final frame is the pose that
        gets rendered, so 'HD' now includes 'hanging correctly'."""
        steps = POLY_SETTLE_STEPS if steps is None else steps
        for i in range(steps):
            self.step(dt)
        return self

    def pos(self, idx):
        return self.particles[idx].p

    def positions(self, idxs):
        return [self.particles[i].p for i in idxs]

    def grid_positions(self, grid):
        return [[self.particles[i].p for i in row] for row in grid]


def strand_mesh(points, r0, r1, segments=7, mat=0, rings_per_seg=1):
    """Skin a settled strand with tapered tube segments - so hair and chains
    are real polygons lit by the same lights as the body, not drawn lines."""
    m = Mesh()
    n = len(points)
    for i in range(n - 1):
        f0 = i / max(1, n - 1)
        f1 = (i + 1) / max(1, n - 1)
        ra = r0 + (r1 - r0) * f0
        rb = r0 + (r1 - r0) * f1
        seg = mesh_capsule(points[i], points[i + 1], ra, rb,
                           segments=segments, rings=rings_per_seg, mat=mat,
                           caps=(i == 0 or i == n - 2))
        m.merge(seg)
    return m


# ---------------------------------------------------------------------------
#  the character rig
# ---------------------------------------------------------------------------

_SPECIES_SHAPE = {
    # species          skull_w skull_h jaw   muzzle ears   horns  extra
    "Robot":          (1.06, 1.02, 0.94, 0.10, "panel", 0.0, "plates"),
    "Alien":          (1.10, 1.18, 0.72, 0.04, "none", 0.0, "smooth"),
    "Demon":          (1.00, 1.04, 0.98, 0.14, "point", 1.0, "ridged"),
    "Oni":            (1.12, 1.00, 1.08, 0.16, "point", 1.0, "ridged"),
    "Dragon":         (0.98, 0.96, 1.02, 0.34, "fin", 0.9, "scaled"),
    "Wolf":           (0.96, 0.98, 1.00, 0.30, "point", 0.0, "furred"),
    "Fox":            (0.92, 0.96, 0.94, 0.32, "point", 0.0, "furred"),
    "Cat":            (0.94, 0.94, 0.90, 0.22, "point", 0.0, "furred"),
    "Bear":           (1.14, 1.02, 1.06, 0.26, "round", 0.0, "furred"),
    "Ape":            (1.08, 0.98, 1.10, 0.24, "round", 0.0, "furred"),
    "Reptile":        (0.98, 0.94, 1.00, 0.30, "fin", 0.3, "scaled"),
    "Skeleton":       (0.96, 1.00, 1.00, 0.18, "none", 0.0, "bone"),
    "Ghost":          (1.02, 1.10, 0.80, 0.06, "none", 0.0, "smooth"),
    "Cyborg":         (1.02, 1.00, 0.96, 0.12, "panel", 0.0, "plates"),
    "Human":          (1.00, 1.00, 1.00, 0.14, "round", 0.0, "smooth"),
    "_default":       (1.00, 1.00, 1.00, 0.16, "round", 0.0, "smooth"),
}

_SURFACE_TWEAK = {
    "plates":  dict(spec=0.55, shine=48.0, facet_line=0.70, metal=0.7, jitter=0.6),
    "smooth":  dict(spec=0.22, shine=26.0, facet_line=0.88, metal=0.0, jitter=0.9),
    "ridged":  dict(spec=0.30, shine=20.0, facet_line=0.66, metal=0.1, jitter=3.4),
    "scaled":  dict(spec=0.40, shine=30.0, facet_line=0.60, metal=0.2, jitter=2.6),
    "furred":  dict(spec=0.12, shine=12.0, facet_line=0.78, metal=0.0, jitter=2.0),
    "bone":    dict(spec=0.34, shine=36.0, facet_line=0.62, metal=0.0, jitter=1.4),
}


def _species_shape(name):
    for key, val in _SPECIES_SHAPE.items():
        if key != "_default" and key.lower() in str(name).lower():
            return val
    return _SPECIES_SHAPE["_default"]


class PolyCharacter:
    """Builds the whole character - skull, jaw, torso, features, hardware -
    as one mesh, and hangs every dangling part off the physics solver."""

    def __init__(self, traits, seed=None, scale=1.0):
        self.traits = traits or {}
        self.seed = seed if seed is not None else _random.randint(0, 1 << 30)
        self.rnd = _random.Random(self.seed)
        self.noise = ValueNoise(self.seed ^ 0x5EED)
        self.scale = scale
        self.mesh = Mesh()
        self.materials = []
        self.world = VerletWorld(seed=self.seed,
                                 wind=(38.0, 0.0, -12.0),
                                 gravity=(0.0, -560.0, 0.0))
        self._deferred = []

        shape = _species_shape(self.traits.get("Species", "Human"))
        (self.skull_w, self.skull_h, self.jaw, self.muzzle,
         self.ear_kind, self.horn, self.surface) = shape

        skin = _hex_to_rgb(self.traits.get("Skin", "#8fa0b8"))
        eye = _hex_to_rgb(self.traits.get("Eye Color", "#38e8ff"))
        self.skin = skin
        self.eye = eye
        tw = _SURFACE_TWEAK.get(self.surface, _SURFACE_TWEAK["smooth"])
        self.jitter_amt = tw["jitter"]

        self.M_SKIN = self._mat(Material(skin, spec=tw["spec"], shine=tw["shine"],
                                         facet_line=tw["facet_line"], metal=tw["metal"],
                                         rim_col=_mix(eye, (255, 255, 255), 0.45),
                                         rim=0.34, ambient=0.20))
        self.M_SKIN_DK = self._mat(Material(_mix(skin, (6, 8, 22), 0.42),
                                            spec=tw["spec"] * 0.7, shine=tw["shine"],
                                            facet_line=tw["facet_line"], metal=tw["metal"],
                                            ambient=0.16))
        self.M_SKIN_LT = self._mat(Material(_mix(skin, (255, 255, 255), 0.30),
                                            spec=tw["spec"], shine=tw["shine"],
                                            facet_line=tw["facet_line"], metal=tw["metal"],
                                            ambient=0.24))
        self.M_EYE = self._mat(Material(eye, spec=0.85, shine=90.0, rim=0.5,
                                        emissive=0.55, ambient=0.5,
                                        rim_col=(255, 255, 255), facet_line=0.95))
        self.M_SCLERA = self._mat(Material((242, 246, 252), spec=0.7, shine=70.0,
                                           ambient=0.45, facet_line=0.94))
        self.M_PUPIL = self._mat(Material((10, 10, 18), spec=0.9, shine=120.0,
                                          ambient=0.10, facet_line=0.98))
        self.M_METAL = self._mat(Material(_mix(skin, (210, 220, 240), 0.55),
                                          spec=0.75, shine=64.0, metal=1.0,
                                          facet_line=0.58, ambient=0.18))
        self.M_DARK = self._mat(Material((22, 24, 34), spec=0.30, shine=30.0,
                                         ambient=0.14, facet_line=0.70))
        self.M_HAIR = self._mat(Material(_mix(skin, (18, 14, 30), 0.72),
                                         spec=0.36, shine=34.0, facet_line=0.74,
                                         rim=0.45, rim_col=eye, ambient=0.15))
        self.M_CLOTH = self._mat(Material(_mix(eye, (30, 26, 52), 0.62),
                                          spec=0.14, shine=14.0, facet_line=0.80,
                                          rim=0.30, ambient=0.20))
        self.M_ACCENT = self._mat(Material(eye, spec=0.6, shine=54.0,
                                           emissive=0.35, ambient=0.35,
                                           facet_line=0.86))

    def _mat(self, m):
        self.materials.append(m)
        return len(self.materials) - 1

    # -- geometry --------------------------------------------------------
    def build(self):
        self._build_torso()
        self._build_skull()
        self._build_face()
        self._build_ears()
        self._build_horns()
        self._build_headwear()
        # everything built so far is the rigid core; what follows is simulated
        self.core_verts = len(self.mesh.verts)
        self._collect_colliders()
        self._build_physics()
        return self

    def _build_torso(self):
        body_t = str(self.traits.get("Body Type", "")).lower()
        bulk = 1.22 if ("heavy" in body_t or "brawler" in body_t or "tank" in body_t) else \
               0.86 if ("slim" in body_t or "lithe" in body_t) else 1.0

        shoulder_y = -132.0
        profile = [
            (46.0 * bulk, -258.0),
            (74.0 * bulk, -226.0),
            (88.0 * bulk, -186.0),
            (92.0 * bulk, shoulder_y),
            (70.0 * bulk, -104.0),
            (48.0 * bulk, -80.0),
        ]
        torso = mesh_lathe(profile, segments=22, mat=self.M_SKIN_DK)
        torso.transform(lambda v: (v[0], v[1], v[2] * 0.66))
        torso.jitter(self.jitter_amt * 1.6, self.noise, freq=0.02)
        self.mesh.merge(torso)

        # deltoids - flattened masses, not spheres, so the shoulder line reads
        for side in (-1, 1):
            cap = mesh_ellipsoid(40.0 * bulk, 30.0 * bulk, 28.0 * bulk,
                                 segments=14, rings=8, mat=self.M_SKIN)
            cap.transform(lambda v: v_add(v, (side * 84.0 * bulk, shoulder_y + 4.0, 2.0)))
            cap.jitter(self.jitter_amt, self.noise, freq=0.05)
            self.mesh.merge(cap)
            arm = mesh_capsule((side * 92.0 * bulk, shoulder_y - 4.0, 0.0),
                               (side * 108.0 * bulk, -236.0, -6.0),
                               30.0 * bulk, 20.0 * bulk,
                               segments=10, rings=4, mat=self.M_SKIN_DK)
            self.mesh.merge(arm)

        # chest plate / collar - an extruded polygon, i.e. genuinely polygonal
        w = 62.0 * bulk
        plate = mesh_prism([(-w, -168.0), (-w * 0.5, -196.0), (w * 0.5, -196.0),
                            (w, -168.0), (w * 0.62, -116.0), (-w * 0.62, -116.0)],
                           44.0, 66.0, mat=self.M_METAL if self.surface == "plates" else self.M_SKIN_LT)
        self.mesh.merge(plate)
        self.shoulder_y = shoulder_y
        self.bulk = bulk

    def _build_skull(self):
        sw = 96.0 * self.skull_w
        sh = 106.0 * self.skull_h

        # cranium: lathe + facet jitter -> a hand-cut low-poly skull, not a ball
        profile = []
        rings = 14
        for i in range(rings + 1):
            t = _math.pi * i / rings
            r = sw * _math.sin(t)
            y = -sh * _math.cos(t)
            # flatten the back of the head and square the crown a little
            r *= 1.0 - 0.10 * _math.cos(t * 2.0)
            profile.append((r, y + 34.0))
        skull = mesh_lathe(profile, segments=22, mat=self.M_SKIN)
        skull.transform(lambda v: (v[0], v[1], v[2] * 0.88))
        skull.jitter(self.jitter_amt * 2.2, self.noise, freq=0.035)
        self.mesh.merge(skull)
        self.skull_r = sw
        self.skull_top = 34.0 + sh
        # one face plane every feature is measured off, so nothing ends up
        # drawn behind the jaw it is supposed to sit in front of
        self.face_z = sw * 0.74

        # jaw / muzzle: separate mass so the profile has a real chin line
        jw = sw * 0.80 * self.jaw
        jaw_front = self.face_z * 0.78 + self.muzzle * 210.0
        jaw = mesh_prism([(-jw, -34.0), (-jw * 0.60, -86.0), (jw * 0.60, -86.0),
                          (jw, -34.0), (jw * 0.88, -2.0), (-jw * 0.88, -2.0)],
                         14.0, jaw_front, mat=self.M_SKIN_DK)
        jaw.jitter(self.jitter_amt * 1.2, self.noise, freq=0.05)
        self.mesh.merge(jaw)
        self.jaw_front = jaw_front

        # brow ridge - one wedge, heavily catches the key light
        bw = sw * 0.94
        brow = mesh_prism([(-bw, 30.0), (-bw * 0.7, 56.0), (bw * 0.7, 56.0),
                           (bw, 30.0), (bw * 0.8, 16.0), (-bw * 0.8, 16.0)],
                          self.face_z * 0.55, self.face_z * 1.02, mat=self.M_SKIN_LT)
        self.mesh.merge(brow)

        # neck
        neck = mesh_capsule((0.0, -70.0, 18.0), (0.0, -128.0, 10.0),
                            30.0, 40.0, segments=14, rings=3, mat=self.M_SKIN_DK)
        self.mesh.merge(neck)

    def _build_face(self):
        sw = self.skull_r
        eye_x = sw * 0.46
        eye_y = 6.0
        eye_z = self.face_z
        eye_r = sw * 0.30

        for side in (-1, 1):
            socket = mesh_ellipsoid(eye_r * 1.22, eye_r * 0.96, eye_r * 0.55,
                                    segments=14, rings=8, mat=self.M_SKIN_DK)
            socket.transform(lambda v: v_add(v, (side * eye_x, eye_y, eye_z - 16.0)))
            self.mesh.merge(socket)

            ball = mesh_ellipsoid(eye_r, eye_r, eye_r * 0.8,
                                  segments=16, rings=10, mat=self.M_SCLERA)
            ball.transform(lambda v: v_add(v, (side * eye_x, eye_y, eye_z)))
            self.mesh.merge(ball)

            iris = mesh_ellipsoid(eye_r * 0.60, eye_r * 0.60, eye_r * 0.28,
                                  segments=16, rings=7, mat=self.M_EYE)
            iris.transform(lambda v: v_add(v, (side * eye_x, eye_y, eye_z + eye_r * 0.66)))
            self.mesh.merge(iris)

            pupil = mesh_ellipsoid(eye_r * 0.26, eye_r * 0.30, eye_r * 0.14,
                                   segments=12, rings=6, mat=self.M_PUPIL)
            pupil.transform(lambda v: v_add(v, (side * eye_x, eye_y, eye_z + eye_r * 0.86)))
            self.mesh.merge(pupil)

        # nose / snout ridge - rides on the front of the jaw mass
        nz = max(self.jaw_front, eye_z) + 4.0
        nose = mesh_prism([(-sw * 0.17, -10.0), (0.0, 20.0), (sw * 0.17, -10.0),
                           (sw * 0.12, -30.0), (-sw * 0.12, -30.0)],
                          nz - 24.0, nz + 14.0 + self.muzzle * 30.0, mat=self.M_SKIN_LT)
        self.mesh.merge(nose)

        # mouth: a recessed dark prism, then teeth for the species that have them
        mw = sw * 0.44
        mz = self.jaw_front
        mouth = mesh_prism([(-mw, -50.0), (-mw * 0.8, -38.0), (mw * 0.8, -38.0),
                            (mw, -50.0), (mw * 0.85, -66.0), (-mw * 0.85, -66.0)],
                           mz - 6.0, mz + 8.0, mat=self.M_DARK)
        self.mesh.merge(mouth)
        if self.surface in ("ridged", "scaled", "furred", "bone"):
            for i in range(6):
                fx = -mw * 0.74 + (mw * 1.48) * i / 5.0
                tooth = mesh_prism([(fx - mw * 0.09, -40.0), (fx, -58.0),
                                    (fx + mw * 0.09, -40.0)],
                                   mz + 2.0, mz + 13.0, mat=self.M_SKIN_LT)
                self.mesh.merge(tooth)

        self.eye_z = eye_z

    def _build_ears(self):
        if self.ear_kind == "none":
            return
        sw = self.skull_r
        for side in (-1, 1):
            if self.ear_kind == "point":
                h = sw * (1.05 + 0.22 * self.rnd.random())
                base = (side * sw * 0.92, 44.0, -6.0)
                tip = (side * sw * (1.30 + 0.25 * self.rnd.random()), 44.0 + h, -28.0)
                ear = mesh_capsule(base, tip, sw * 0.30, sw * 0.045,
                                   segments=8, rings=4, mat=self.M_SKIN)
            elif self.ear_kind == "round":
                ear = mesh_ellipsoid(sw * 0.20, sw * 0.32, sw * 0.12,
                                     segments=12, rings=7, mat=self.M_SKIN)
                ear.transform(lambda v: v_add(v, (side * sw * 0.98, 24.0, -6.0)))
            elif self.ear_kind == "fin":
                pts = [(0.0, 0.0), (sw * 0.55, sw * 0.30), (sw * 0.78, sw * 0.02),
                       (sw * 0.52, -sw * 0.30), (0.0, -sw * 0.18)]
                pts = [(side * (sw * 0.86 + x), 26.0 + y) for x, y in pts]
                ear = mesh_prism(pts, -18.0, 4.0, mat=self.M_SKIN_LT)
            else:  # panel
                pts = [(0.0, -sw * 0.30), (sw * 0.34, -sw * 0.34),
                       (sw * 0.40, sw * 0.26), (0.0, sw * 0.30)]
                pts = [(side * (sw * 0.88 + x), 22.0 + y) for x, y in pts]
                ear = mesh_prism(pts, -26.0, 10.0, mat=self.M_METAL)
            ear.jitter(self.jitter_amt * 0.8, self.noise, freq=0.06)
            self.mesh.merge(ear)

    def _build_horns(self):
        if self.horn <= 0.0:
            return
        sw = self.skull_r
        for side in (-1, 1):
            n = 1 + (1 if self.horn > 0.8 and self.rnd.random() < 0.45 else 0)
            for k in range(n):
                base = (side * sw * (0.56 + 0.22 * k), self.skull_top - 18.0 - 26.0 * k, -8.0)
                seg = base
                r = sw * (0.22 - 0.05 * k)
                curl = self.rnd.uniform(0.25, 0.75) * self.horn
                for i in range(5):
                    t = i / 5.0
                    nxt = v_add(seg, (side * (16.0 + 26.0 * t) * curl,
                                      34.0 - 8.0 * t,
                                      -10.0 - 18.0 * t))
                    self.mesh.merge(mesh_capsule(seg, nxt, r * (1 - t * 0.78),
                                                 r * (1 - (t + 0.2) * 0.78),
                                                 segments=8, rings=2,
                                                 mat=self.M_SKIN_LT))
                    seg = nxt

    def _build_headwear(self):
        wear = str(self.traits.get("Headwear", "") or "").lower()
        sw = self.skull_r
        top = self.skull_top
        if not wear or wear in ("none", "bare"):
            return
        if "crown" in wear or "halo" in wear:
            ring = mesh_lathe([(sw * 0.92, top - 26.0), (sw * 1.02, top - 10.0),
                               (sw * 0.96, top + 4.0)], segments=24,
                              mat=self.M_METAL, close_top=False, close_bottom=False)
            self.mesh.merge(ring)
            for i in range(7):
                a = _math.tau * i / 7.0 - _math.pi / 2
                px, pz = _math.cos(a) * sw * 0.96, _math.sin(a) * sw * 0.96 * 0.88
                spike = mesh_capsule((px, top - 4.0, pz), (px * 1.05, top + 52.0, pz * 1.05),
                                     sw * 0.10, sw * 0.012, segments=6, rings=2,
                                     mat=self.M_METAL)
                self.mesh.merge(spike)
        elif "helmet" in wear or "hood" in wear or "mask" in wear:
            shell = mesh_ellipsoid(sw * 1.10, sw * 1.06, sw * 1.00,
                                   segments=20, rings=11,
                                   mat=self.M_METAL if "helmet" in wear else self.M_CLOTH)
            shell.transform(lambda v: v_add(v, (0.0, 34.0, -6.0)))
            shell.jitter(self.jitter_amt * 1.4, self.noise, freq=0.04)
            self.mesh.merge(shell)
        elif "cap" in wear or "hat" in wear or "beanie" in wear:
            cap = mesh_lathe([(sw * 1.04, top - 60.0), (sw * 1.02, top - 12.0),
                              (sw * 0.72, top + 26.0), (sw * 0.22, top + 44.0)],
                             segments=20, mat=self.M_CLOTH)
            self.mesh.merge(cap)
        elif "horn" in wear or "antenna" in wear:
            pass  # handled by the physics pass

    # -- physics ---------------------------------------------------------
    def _collect_colliders(self):
        sw = self.skull_r
        self.world.colliders = [
            SphereCollider((0.0, 34.0, 0.0), sw * 1.02),
            CapsuleCollider((0.0, -70.0, 14.0), (0.0, -130.0, 8.0), 44.0),
            CapsuleCollider((0.0, -140.0, 6.0), (0.0, -236.0, 2.0),
                            108.0 * getattr(self, "bulk", 1.0)),
        ]

    def _build_physics(self):
        """Hair, chains, pendants and cloth are simulated, settled, then
        skinned as polygons. Everything below is geometry the old renderer
        simply did not have."""
        sw = self.skull_r
        top = self.skull_top
        wear = str(self.traits.get("Headwear", "") or "").lower()
        hair_ok = self.surface in ("furred", "smooth", "bone") and "helmet" not in wear

        self.strands = []

        if hair_ok:
            rows = 2 if self.surface == "furred" else 2
            per_row = 13 if self.surface == "furred" else 11
            for row in range(rows):
                shell = 1.0 - row * 0.26
                for i in range(per_row):
                    a = (_math.pi * 1.30) * (i / (per_row - 1.0)) - _math.pi * 0.65
                    ax = _math.sin(a) * sw * 0.92 * shell
                    az = -_math.cos(a) * sw * 0.70 * shell - 8.0
                    ay = top - 18.0 - abs(_math.sin(a)) * 30.0 - row * 16.0
                    idx = self.world.strand(
                        (ax, ay, az),
                        v_norm((ax * 0.55, 0.40, az * 0.55)),
                        count=9, seg_len=sw * 0.26,
                        stiff=0.86, bend=0.17, jitter=sw * 0.09,
                        radius=sw * 0.11, mass=1.0 + 0.2 * row)
                    self.strands.append((idx, sw * 0.125, sw * 0.030, self.M_HAIR))

        if self.surface in ("furred",) or "whisker" in str(self.traits.get("Mouth", "")).lower():
            for side in (-1, 1):
                for k in range(3):
                    anchor = (side * sw * 0.34, -34.0 - k * 9.0, self.eye_z + 30.0)
                    idx = self.world.strand(
                        anchor, (side * 0.92, -0.10 - 0.08 * k, 0.28),
                        count=5, seg_len=sw * 0.26, stiff=0.7, bend=0.42,
                        radius=0.0)
                    self.strands.append((idx, sw * 0.030, sw * 0.008, self.M_SKIN_LT))

        if "antenna" in wear or self.surface == "plates":
            for side in (-1, 1):
                idx = self.world.strand(
                    (side * sw * 0.52, top - 6.0, -6.0), (side * 0.22, 1.0, -0.14),
                    count=6, seg_len=sw * 0.24, stiff=0.98, bend=0.75,
                    radius=0.0)
                self.strands.append((idx, sw * 0.035, sw * 0.018, self.M_METAL))
                self.antenna_tip = idx[-1]

        # a pendant on a chain - swings out to its own rest angle
        self.pendant = None
        if self.rnd.random() < 0.72:
            anchor = (0.0, -132.0, 46.0)
            idx = self.world.strand(anchor, (0.06, -1.0, 0.18),
                                    count=8, seg_len=13.0, stiff=0.99,
                                    bend=0.10, mass=1.4)
            self.strands.append((idx, 4.6, 4.0, self.M_METAL))
            self.pendant = idx[-1]

        # cloth: cape / scarf hanging off the shoulders
        self.cloth_grid = None
        body_t = str(self.traits.get("Clothes", self.traits.get("Body Type", ""))).lower()
        if "cape" in body_t or "cloak" in body_t or "hood" in wear or self.rnd.random() < 0.5:
            cols, rows = 11, 9
            span = 300.0 * getattr(self, "bulk", 1.0)
            self.cloth_grid = self.world.cloth(
                origin=(-span * 0.5, self.shoulder_y + 34.0, -62.0),
                right=(span / (cols - 1), 0.0, 3.0),
                down=(0.0, -36.0, -4.0),
                cols=cols, rows=rows, stiff=0.94, shear=0.5, bend=0.22, mass=0.9)

        self.world.settle()

        # skin the settled rig
        for idx, r0, r1, mat in self.strands:
            pts = self.world.positions(idx)
            self.mesh.merge(strand_mesh(pts, r0, r1, segments=7, mat=mat))

        if self.pendant is not None:
            p = self.world.pos(self.pendant)
            gem = mesh_ellipsoid(17.0, 21.0, 11.0, segments=8, rings=5, mat=self.M_ACCENT)
            gem.transform(lambda v: v_add(v, p))
            self.mesh.merge(gem)

        if self.cloth_grid is not None:
            grid = self.world.grid_positions(self.cloth_grid)
            self.mesh.merge(mesh_from_grid(grid, mat=self.M_CLOTH, double_sided=True))

    # -- output ----------------------------------------------------------
    def render(self, width, height, light=None, margin=0.88, y_bias=0.0):
        cam = Camera(width, height, focal=width * 0.95, dist=880.0)
        core = self.mesh.verts[:getattr(self, "core_verts", len(self.mesh.verts))]
        cam.fit(self.mesh.verts, margin=margin, y_bias=y_bias, centre_on=core)
        light = light or Light()
        return render_mesh(self.mesh, cam, light, self.materials,
                           fog=(_mix(self.skin, (4, 6, 16), 0.88),
                                cam.dist + 40.0, cam.dist + 340.0))


# ---------------------------------------------------------------------------
#  faceted background  (low-poly crystal field, lit by the same lights)
# ---------------------------------------------------------------------------

def render_poly_background(width, height, col_a, col_b, accent, seed=0, cells=11):
    if not _HAS_PIL_POLY:
        return None
    rnd = _random.Random(seed ^ 0xB6B6)
    img = _PILImage.new("RGB", (width, height), _mix(col_a, (0, 0, 0), 0.35))
    draw = _PILDraw.Draw(img, "RGBA")
    step_x = width / cells
    step_y = height / cells
    pts = [[(c * step_x + rnd.uniform(-0.34, 0.34) * step_x,
             r * step_y + rnd.uniform(-0.34, 0.34) * step_y)
            for c in range(cells + 1)] for r in range(cells + 1)]
    for r in range(cells):
        for c in range(cells):
            quad = [pts[r][c], pts[r][c + 1], pts[r + 1][c + 1], pts[r + 1][c]]
            t = (r / cells) * 0.7 + (c / cells) * 0.3
            base = _mix(col_a, col_b, t)
            k = rnd.uniform(-0.10, 0.10)
            base = _mix(base, (255, 255, 255) if k > 0 else (0, 0, 0), abs(k))
            for tri in ((0, 1, 2), (0, 2, 3)):
                shade = _mix(base, accent, rnd.uniform(0.0, 0.22))
                draw.polygon([quad[i] for i in tri], fill=(*shade, 255))
    # vignette
    vg = _PILImage.new("L", (width, height), 0)
    vd = _PILDraw.Draw(vg)
    vd.ellipse([-width * 0.25, -height * 0.25, width * 1.25, height * 1.25], fill=255)
    vg = vg.filter(_PILFilter.GaussianBlur(width / 14.0))
    dark = _PILImage.new("RGB", (width, height), _mix(col_a, (0, 0, 0), 0.72))
    img = _PILImage.composite(img, dark, vg)
    return img


# ---------------------------------------------------------------------------
#  the new HD entry point
# ---------------------------------------------------------------------------

def render_poly_physics_portrait(traits, size=1080, seed=None, supersample=None,
                                 log_cb=None):
    """Render just the polygon/physics character, as an RGBA layer."""
    if not _HAS_PIL_POLY:
        raise RuntimeError("Pillow is required for the polygon HD renderer")
    ss = int(supersample or POLY_SUPERSAMPLE)
    W = H = int(size * ss)
    if log_cb:
        log_cb(f"[polyHD] building rig ({W}x{H} internal, {ss}x supersample)")

    char = PolyCharacter(traits, seed=seed).build()
    if log_cb:
        log_cb(f"[polyHD] {len(char.mesh)} facets, "
               f"{len(char.world.particles)} particles, "
               f"{len(char.world.constraints)} constraints")

    layer = char.render(W, H, margin=0.88, y_bias=-0.035)
    if ss > 1:
        layer = layer.resize((size, size), _PILImage.LANCZOS)
    return layer, char


def generate_nft_character_poly(size=1080, seed=None, override_traits=None,
                                log_cb=None, supersample=None):
    """Drop-in replacement for the classic HD generator.

    Same signature, same return value ``(PIL.Image, traits)`` - so every
    existing caller (the NFT batch, the reel pipeline, the TrippyGram UI, the
    Acacia bridge) picks this up with no changes.
    """
    pick = NS_get("_pick_traits")
    traits = pick(override_traits=override_traits, seed=seed) if pick else (override_traits or {})

    if seed is not None:
        _random.seed(seed)

    skin = _hex_to_rgb(_maybe_hex(traits.get("Skin", "#8fa0b8")))
    eye = _hex_to_rgb(_maybe_hex(traits.get("Eye Color", "#38e8ff")))
    bg_a = _mix(_mix(eye, (10, 12, 30), 0.80), skin, 0.18)
    bg_b = _mix(_mix(skin, (6, 6, 20), 0.74), eye, 0.22)

    ss = int(supersample or POLY_SUPERSAMPLE)
    bgW = size * 2
    bg = render_poly_background(bgW, bgW, bg_a, bg_b, eye,
                                seed=(seed or 0) ^ 0x1234, cells=13)
    bg = bg.resize((size, size), _PILImage.LANCZOS).convert("RGBA")

    layer, char = render_poly_physics_portrait(traits, size=size, seed=seed,
                                               supersample=ss, log_cb=log_cb)

    # contact shadow, grounded off the settled silhouette
    shadow = layer.split()[3].filter(_PILFilter.GaussianBlur(size / 42.0))
    sh_img = _PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
    sh_img.putalpha(shadow.point(lambda a: int(a * 0.55)))
    bg.alpha_composite(sh_img, (int(size * 0.012), int(size * 0.020)))

    bg.alpha_composite(layer)

    out = bg.convert("RGB")
    out = _draw_poly_hud(out, traits, skin, eye, size)
    return out, traits


def _maybe_hex(v):
    fn = NS_get("_hex")
    if fn is not None and isinstance(v, str) and not v.startswith("#"):
        try:
            return fn(v)
        except Exception:
            return v
    return v


def NS_get(name):
    """Look a name up in the shared ACACIA namespace at call time."""
    return globals().get(name)


def _draw_poly_hud(img, traits, skin, eye, size):
    """Card furniture, drawn with the original HUD helpers so the look of the
    lettering and the trait pills is unchanged - only the art underneath is
    new."""
    load_font = NS_get("_load_font")
    text_out = NS_get("_draw_text_outlined")
    badge = NS_get("_draw_trait_badge")
    if not (load_font and text_out):
        return img

    k = size / 1080.0
    # _draw_trait_badge looks up the literal keys 18 and 22, so map those keys
    # onto resolution-scaled faces instead of hard 18/22 pixel text.
    sizes = {18: max(9, int(19 * k)), 22: max(11, int(23 * k)),
             "title": max(20, int(62 * k)), "sub": max(12, int(28 * k))}
    raw = load_font(sorted(set(sizes.values())))
    fonts = {18: raw[sizes[18]], 22: raw[sizes[22]]}
    big = raw[sizes["title"]]
    mid = raw[sizes["sub"]]

    band_h = int(size * 0.185)
    band = _PILImage.new("RGBA", (size, band_h), (*_mix(skin, (0, 0, 0), 0.88), 210))
    top = img.crop((0, size - band_h, size, size)).convert("RGBA")
    img.paste(_PILImage.alpha_composite(top, band).convert("RGB"), (0, size - band_h))

    draw = _PILDraw.Draw(img, "RGBA")
    accent = _mix(eye, (255, 255, 255), 0.25)

    name = str(traits.get("Species", "ACACIA")).upper()
    text_out(draw, (int(40 * k), int(30 * k)), name, big, accent, (0, 0, 0),
             stroke=max(2, int(4 * k)))
    rarity = traits.get("Rarity") or traits.get("Rare Trait") or "POLY-HD"
    text_out(draw, (int(44 * k), int(30 * k) + int(sizes["title"] * 1.12)),
             f"[ {str(rarity).upper()}  \u00b7  POLY-HD ]", mid,
             _mix(eye, (255, 255, 255), 0.55), (0, 0, 0), stroke=max(2, int(3 * k)))

    if badge:
        rows = 3
        col_w = size // 2
        x0, y0 = int(26 * k), size - band_h + int(14 * k)
        row_h = (band_h - int(24 * k)) // rows
        shown = 0
        for key in ("Species", "Eyes", "Mouth", "Headwear", "Body Type", "Color Scheme"):
            val = traits.get(key)
            if not val or str(val).lower() == "none":
                continue
            col, row = divmod(shown, rows)
            if col > 1:
                break
            val_s = str(val)
            if len(val_s) > 14:
                val_s = val_s[:13] + "\u2026"
            try:
                badge(draw, (x0 + col * col_w, y0 + row * row_h),
                      key.upper(), val_s, fonts, eye)
            except Exception:
                break
            shown += 1
    return img


# ---------------------------------------------------------------------------
#  install the override  (the classic renderer stays reachable, untouched)
# ---------------------------------------------------------------------------

generate_nft_character_classic = generate_nft_character            # noqa: F821


def generate_nft_character(size=1080, seed=None, override_traits=None):
    """HD NFT character.

    Routes to the polygon/physics renderer unless it is disabled, in which
    case the original 3x-supersampled renderer is used verbatim.
    """
    if POLY_HD_ENABLED and _HAS_PIL_POLY:
        try:
            return generate_nft_character_poly(size=size, seed=seed,
                                               override_traits=override_traits)
        except Exception as exc:                       # pragma: no cover
            try:
                print(f"[polyHD] falling back to classic renderer: {exc!r}")
            except Exception:
                pass
    return generate_nft_character_classic(size=size, seed=seed,
                                          override_traits=override_traits)


def poly_hd(enabled=True):
    """Toggle the polygon/physics renderer at runtime."""
    global POLY_HD_ENABLED
    POLY_HD_ENABLED = bool(enabled)
    return POLY_HD_ENABLED


def _poly_standalone_test(n=3, out_dir="./test_poly", size=1080, seed=None):
    """`python acacia.py --test-poly` - render the new HD path only."""
    _os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i in range(n):
        s = (seed + i) if seed is not None else _random.randint(0, 1 << 28)
        img, traits = generate_nft_character_poly(size=size, seed=s,
                                                  log_cb=lambda m: print(m))
        p = _os.path.join(out_dir, f"poly_{s}.png")
        img.save(p)
        paths.append(p)
        print(f"[polyHD] {p}  species={traits.get('Species')}")
    return paths

// OpenChess PCB redesign - printable enclosure (parametric, driven by enc_params.scad written by tools/gen_enclosure.py)
// Coordinates follow the PCB: x to the right, y "down" the board (rank 8 at small y), z up from the PCB top surface.
// Parts (select with -D part="..."):  top_q00 top_q10 top_q01 top_q11   tray_00 tray_10 tray_01 tray_11   cover_0 cover_1
include <enc_params.scad>

part = "top_q00";
$fn = 48;

T_PLATE   = 4.0;    // playing-surface plate thickness
PLATE_GAP = 3.0;    // space between PCB top and plate bottom (LEDs are 1.6 mm)
DISC_D    = 12.4;   // iron disc pocket diameter (disc 12 x 1 mm)
DISC_H    = 1.3;
LED_D     = 9.0;    // LED light pocket diameter
LED_SKIN  = 0.8;    // translucent skin left above each LED
WALL      = 2.5;
FLOOR     = 2.0;
STANDOFF  = 2.5;    // PCB bottom above the tray floor
RIM_H     = STANDOFF + 1.6 + PLATE_GAP;   // tray wall height above the floor top = plate underside level
COVER_T   = 2.0;
SCREW_D   = 3.4;    // M3 clearance
TAP_D     = 2.6;    // M3 self-tapping blind hole in the plate

function sq_cx(f) = GRID_X0 + PITCH * (f + 0.5);
function sq_cy(r) = GRID_Y0 + PITCH * (7 - r + 0.5);

// ---------------------------------------------------------------- top plate quadrant
module top_quadrant(qx, qy) {
    x0 = qx == 0 ? 0 : GRID_X0 + 4 * PITCH;  x1 = qx == 0 ? GRID_X0 + 4 * PITCH : W;
    y0 = qy == 0 ? 0 : GRID_Y0 + 4 * PITCH;  y1 = qy == 0 ? GRID_Y0 + 4 * PITCH : STRIP_Y;
    difference() {
        union() {
            translate([x0, y0, 0]) cube([x1 - x0, y1 - y0, T_PLATE]);
            // bosses resting on the PCB at the free square corners inside this quadrant
            for (i = [1 : 7], j = [1 : 7]) {
                px = GRID_X0 + PITCH * i; py = GRID_Y0 + PITCH * j;
                if (px > x0 && px < x1 && py > y0 && py < y1 && (i % 2 == 0) && (j % 2 == 0))
                    translate([px, py, -PLATE_GAP]) cylinder(d = 6, h = PLATE_GAP + 0.01);
            }
        }
        for (f = [0 : 7], r = [0 : 7]) {
            cx = sq_cx(f); cy = sq_cy(r);
            if (cx > x0 && cx < x1 && cy > y0 && cy < y1) {
                translate([cx, cy, -1]) cylinder(d = DISC_D, h = DISC_H + 1);                 // iron disc pocket (from below)
                translate([cx, cy + LED_DY, -1]) cylinder(d = LED_D, h = T_PLATE - LED_SKIN + 1); // LED light pocket (from below)
            }
        }
        // 0.4 mm grooves on top along the square edges
        for (i = [0 : 8]) {
            gx = GRID_X0 + PITCH * i;
            if (gx >= x0 - 0.01 && gx <= x1 + 0.01) translate([gx - 0.25, max(y0, GRID_Y0), T_PLATE - 0.4]) cube([0.5, min(y1, GRID_Y0 + 8 * PITCH) - max(y0, GRID_Y0), 1]);
            gy = GRID_Y0 + PITCH * i;
            if (gy >= y0 - 0.01 && gy <= y1 + 0.01) translate([max(x0, GRID_X0), gy - 0.25, T_PLATE - 0.4]) cube([min(x1, GRID_X0 + 8 * PITCH) - max(x0, GRID_X0), 0.5, 1]);
        }
        // self-tapping M3 holes at the PCB mounting holes inside this quadrant
        for (h = MH) if (h[0] > x0 && h[0] < x1 && h[1] > y0 && h[1] < y1)
            translate([h[0], h[1], -1]) cylinder(d = TAP_D, h = 3 + 1);
        // file letters / rank numbers engraved in the margins
        if (qy == 0) for (f = [0 : 7]) if (sq_cx(f) > x0 && sq_cx(f) < x1)
            translate([sq_cx(f), 5, T_PLATE - 0.5]) linear_extrude(1) text(chr(97 + f), size = 5, halign = "center", valign = "center");
        if (qx == 1) for (r = [0 : 7]) if (sq_cy(r) > y0 && sq_cy(r) < y1)
            translate([W - 5, sq_cy(r), T_PLATE - 0.5]) linear_extrude(1) text(str(r + 1), size = 5, halign = "center", valign = "center");
    }
}

// ---------------------------------------------------------------- tray (4 pieces)
module tray_full() {
    difference() {
        union() {
            translate([-WALL, -WALL, -STANDOFF - 1.6 - FLOOR]) cube([W + 2 * WALL, H + 2 * WALL, FLOOR]);           // floor
            difference() {                                                                                      // wall
                translate([-WALL, -WALL, -STANDOFF - 1.6 - FLOOR]) cube([W + 2 * WALL, H + 2 * WALL, FLOOR + RIM_H]);
                translate([0, 0, -STANDOFF - 1.6 - 0.01]) cube([W, H, FLOOR + RIM_H + 1]);
            }
            for (h = MH) translate([h[0], h[1], -STANDOFF - 1.6 - 0.01]) cylinder(d = 7, h = STANDOFF + 0.01);       // PCB standoffs
            for (i = [2 : 2 : 6], j = [2 : 2 : 6])                                                                  // PCB support studs
                translate([GRID_X0 + PITCH * i, GRID_Y0 + PITCH * j, -STANDOFF - 1.6 - 0.01]) cylinder(d = 6, h = STANDOFF + 0.01);
        }
        for (h = MH) translate([h[0], h[1], -STANDOFF - 1.6 - FLOOR - 1]) cylinder(d = SCREW_D, h = FLOOR + STANDOFF + 2);
        for (h = MH) translate([h[0], h[1], -STANDOFF - 1.6 - FLOOR - 0.01]) cylinder(d1 = 6.5, d2 = SCREW_D, h = 1.6);  // countersink
        // USB-C opening in the bottom wall (connector shell 3.2 mm tall on the PCB)
        translate([J1_X - 6, H - 1, -0.5]) cube([12, WALL + 2, 4.5]);
        // module variant: the ESP32 antenna overhangs the bottom edge -> notch in the wall
        if (VARIANT == "module") translate([ANT_X0, H - 1, -STANDOFF - 1.6 - FLOOR - 1]) cube([ANT_X1 - ANT_X0, WALL + 2, FLOOR + RIM_H + 2]);
    }
}
module tray_piece(ix, iy) {
    xs = W / 2; ys = H / 2;
    intersection() {
        tray_full();
        translate([ix == 0 ? -WALL - 1 : xs, iy == 0 ? -WALL - 1 : ys, -50]) cube([W / 2 + WALL + 1, H / 2 + WALL + 1, 100]);
    }
}

// ---------------------------------------------------------------- strip cover (2 pieces)
module cover_full() {
    skirt = COVER_INNER_H - PLATE_GAP;   // the skirt stands on the tray rim (rim = PLATE_GAP above the PCB)
    difference() {
        union() {
            translate([-WALL, STRIP_Y, PLATE_GAP + skirt]) cube([W + 2 * WALL, H - STRIP_Y + WALL, COVER_T]);   // top
            difference() {                                                                                   // skirt
                translate([-WALL, STRIP_Y, PLATE_GAP]) cube([W + 2 * WALL, H - STRIP_Y + WALL, skirt + 0.01]);
                translate([0, STRIP_Y - 1, PLATE_GAP - 0.01]) cube([W, H - STRIP_Y + 1, skirt + 1]);
            }
            // lip under the top-plate edge (keeps the plate and cover aligned)
            translate([0, STRIP_Y, PLATE_GAP + skirt - 3]) cube([W, 2, 3]);
        }
        translate([J2_X - 6, J2_Y - 5, 0]) cube([12, 10, 100]);                                               // J2 5 V cable
        translate([DL1_X, DL1_Y, 0]) cylinder(d = 2.5, h = 100);                                               // power LED light pipe
        if (VARIANT == "module") for (p = [[SW1_X, SW1_Y], [SW2_X, SW2_Y]]) translate([p[0], p[1], 0]) cylinder(d = 4.5, h = 100);
        if (VARIANT == "nodemcu") translate([DEV_USB_X0, DEV_USB_Y0, 0]) cube([DEV_USB_X1 - DEV_USB_X0, DEV_USB_Y1 - DEV_USB_Y0, 100]);
        if (VARIANT == "nodemcu") translate([W - 30, STRIP_Y + 8, 0]) cube([20, 12, 100]);                     // ventilation / access
        if (BATTERY) {
            translate([J5_X - 6, J5_Y - 6, 0]) cube([12, 12, 100]);                                             // battery cable
            translate([SW3_X, SW3_Y, 0]) cylinder(d = 4.5, h = 100);                                            // power key
            translate([JP1_X - 6, JP1_Y - 5, 0]) cube([12, 10, 100]);                                           // jumper access
        }
    }
}
module cover_piece(ix) {
    intersection() {
        cover_full();
        translate([ix == 0 ? -WALL - 1 : W / 2, STRIP_Y - 1, -50]) cube([W / 2 + WALL + 1, H + 10, 100]);
    }
}

if (part == "top_q00") top_quadrant(0, 0);
if (part == "top_q10") top_quadrant(1, 0);
if (part == "top_q01") top_quadrant(0, 1);
if (part == "top_q11") top_quadrant(1, 1);
if (part == "tray_00") tray_piece(0, 0);
if (part == "tray_10") tray_piece(1, 0);
if (part == "tray_01") tray_piece(0, 1);
if (part == "tray_11") tray_piece(1, 1);
if (part == "cover_0") cover_piece(0);
if (part == "cover_1") cover_piece(1);

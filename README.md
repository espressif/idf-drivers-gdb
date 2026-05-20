# idf-drivers-gdb

`idf-drivers-gdb` provides Python GDB commands for debugging ESP-IDF drivers.

## Available Commands

- [`framebuffer_display`](#framebuffer_display): Read LCD framebuffer memory from
  the target and render the image on the host side.

## Installation

```bash
python3 -m pip install idf-drivers-gdb
```

ESP-IDF loads this package from the generated GDB init files. If the package is
installed in the Python environment used by GDB, importing `idf_drivers_gdb`
registers the commands automatically.

## framebuffer_display

`framebuffer_display` reads LCD framebuffer memory from the target, converts the
pixel data, writes an image file, and can open it with the host system image viewer.

### Prerequisites

Use a host environment with a default image viewer.

PNG output is implemented with the Python standard library. If the image viewer
cannot be opened automatically, the command still writes the image file and prints its path.

### Command Syntax

```bash
(gdb) framebuffer_display <gdb-expression/address> <width_pixels> <height_pixels> \
    <rgb565|bgr565|rgb888|bgr888|argb8888|rgba8888|bgra8888> [-s <bytes>] \
    [-c <x,y,w,h>] [-o <path>] [-n]
```

For users who prefer named parameters, the long-option syntax is still supported:

```bash
(gdb) framebuffer_display --expr <gdb-expression> --width <pixels> --height <pixels> \
    --format <rgb565|bgr565|rgb888|bgr888|argb8888|rgba8888|bgra8888> [--stride <bytes>] \
    [--crop <x,y,w,h>] [--output <path>] [--no-show]
```

or

```bash
(gdb) framebuffer_display --addr <address> --width <pixels> --height <pixels> \
    --format <rgb565|bgr565|rgb888|bgr888|argb8888|rgba8888|bgra8888> [--stride <bytes>] \
    [--crop <x,y,w,h>] [--output <path>] [--no-show]
```

### Argument Reference

- `--addr` / `-a`: Start address of framebuffer memory.
- `--expr` / `-e`: GDB expression to evaluate as the framebuffer address.
- `--width` / `-w`: Full framebuffer width in pixels.
- `--height` / `-h`: Full framebuffer height in pixels.
- `--format` / `-f`: Pixel format of the framebuffer.
  Supported formats: `rgb565`, `bgr565`, `rgb888`, `bgr888`, `argb8888`,
  `rgba8888`, `bgra8888`.
- `--stride` / `-s`: Bytes per framebuffer row in memory.
  If omitted, it defaults to `width * bytes_per_pixel`.
- `--crop` / `-c`: Crop region in full-frame coordinates: `x,y,w,h`.
- `--output` / `-o`: Output image path.
  Default is `framebuffer_display.png` in the system temporary directory.
  Use a `.ppm` suffix to write raw PPM output instead of PNG.
- `--no-show` / `-n`: Export only. Do not open the image viewer.

### RGB Panel Example

```bash
(gdb) b esp_lcd_panel_draw_bitmap
(gdb) c
(gdb) framebuffer_display "(uintptr_t)((esp_rgb_panel_t *)panel)->fbs[0]" 800 480 rgb565
```

### Troubleshooting

- `Undefined command: "framebuffer_display"`:
  Install `idf-drivers-gdb` in the Python environment used by GDB, then restart
  the GDB session.
- `No symbol "<name>" in current context`:
  Use `info args` / `info locals` to verify symbol visibility.
- Image viewer does not open:
  Open the printed image path manually, or pass `--no-show` to export only.

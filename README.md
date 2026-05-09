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
pixel data, writes a `.ppm` file, and can render the image directly in the host
terminal.

### Prerequisites

Use a terminal that can display terminal images, such as Kitty, WezTerm, or
iTerm2 with image protocol support.

The package depends on `term-image` for host-side image rendering. If terminal
rendering is not available, the command still writes a `.ppm` file that can be
opened manually.

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
- `--output` / `-o`: Output image path (`.ppm`).
  Default is `framebuffer_display.ppm` in the system temporary directory.
- `--no-show` / `-n`: Export only. Do not render in terminal.

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
- Terminal prints raw image protocol text instead of image:
  Use a compatible terminal or pass `--no-show` and open the generated `.ppm`
  file manually.

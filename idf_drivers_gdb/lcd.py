# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
#
# GDB extension for dumping and displaying framebuffer content.

from __future__ import annotations

import argparse
import binascii
import os
import platform
import shlex
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path
from typing import NoReturn

import gdb  # type: ignore[import-not-found]

OptionValue = int | str | bool

SUPPORTED_FORMATS = {'rgb565', 'bgr565', 'rgb888', 'bgr888', 'argb8888', 'rgba8888', 'bgra8888'}


def _parse_int(value: str) -> int:
    return int(value, 0)


def _parse_address(value: str) -> int:
    try:
        return int(gdb.parse_and_eval(value))
    except gdb.error as err:
        raise gdb.GdbError(f'failed to evaluate address "{value}": {err}') from err


def _to_rgb_bytes(raw: bytes, width: int, height: int, stride: int, pix_fmt: str, x_offset: int = 0) -> bytes:
    if stride <= 0:
        raise gdb.GdbError('stride must be greater than zero')

    expected_size = stride * height
    if len(raw) < expected_size:
        raise gdb.GdbError('framebuffer read returned fewer bytes than expected')

    out = bytearray(width * height * 3)
    out_index = 0

    if pix_fmt in {'rgb565', 'bgr565'}:
        required_row_bytes = (x_offset + width) * 2
        if stride < required_row_bytes:
            raise gdb.GdbError('stride is smaller than one 16-bit row')
        for y in range(height):
            row_start = y * stride
            for x in range(width):
                pixel_offset = row_start + (x + x_offset) * 2
                pixel = raw[pixel_offset] | (raw[pixel_offset + 1] << 8)
                if pix_fmt == 'rgb565':
                    red = ((pixel >> 11) & 0x1F) * 255 // 31
                    blue = (pixel & 0x1F) * 255 // 31
                else:
                    blue = ((pixel >> 11) & 0x1F) * 255 // 31
                    red = (pixel & 0x1F) * 255 // 31
                green = ((pixel >> 5) & 0x3F) * 255 // 63
                out[out_index] = red
                out[out_index + 1] = green
                out[out_index + 2] = blue
                out_index += 3
    elif pix_fmt in {'rgb888', 'bgr888'}:
        required_row_bytes = (x_offset + width) * 3
        if stride < required_row_bytes:
            raise gdb.GdbError('stride is smaller than one 24-bit row')
        for y in range(height):
            row_start = y * stride
            for x in range(width):
                pixel_offset = row_start + (x + x_offset) * 3
                if pix_fmt == 'rgb888':
                    out[out_index] = raw[pixel_offset]
                    out[out_index + 1] = raw[pixel_offset + 1]
                    out[out_index + 2] = raw[pixel_offset + 2]
                else:
                    out[out_index] = raw[pixel_offset + 2]
                    out[out_index + 1] = raw[pixel_offset + 1]
                    out[out_index + 2] = raw[pixel_offset]
                out_index += 3
    elif pix_fmt in {'argb8888', 'rgba8888', 'bgra8888'}:
        required_row_bytes = (x_offset + width) * 4
        if stride < required_row_bytes:
            raise gdb.GdbError('stride is smaller than one 32-bit row')
        for y in range(height):
            row_start = y * stride
            for x in range(width):
                pixel_offset = row_start + (x + x_offset) * 4
                if pix_fmt == 'argb8888':
                    out[out_index] = raw[pixel_offset + 1]
                    out[out_index + 1] = raw[pixel_offset + 2]
                    out[out_index + 2] = raw[pixel_offset + 3]
                elif pix_fmt == 'bgra8888':
                    out[out_index] = raw[pixel_offset + 2]
                    out[out_index + 1] = raw[pixel_offset + 1]
                    out[out_index + 2] = raw[pixel_offset]
                else:
                    out[out_index] = raw[pixel_offset]
                    out[out_index + 1] = raw[pixel_offset + 1]
                    out[out_index + 2] = raw[pixel_offset + 2]
                out_index += 3
    else:
        raise gdb.GdbError(f'unsupported pixel format: {pix_fmt}')

    return bytes(out)


def _write_ppm(path: str, width: int, height: int, rgb_data: bytes) -> None:
    header = f'P6\n{width} {height}\n255\n'.encode('ascii')
    with open(path, 'wb') as f:
        f.write(header)
        f.write(rgb_data)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    payload = chunk_type + data
    crc = binascii.crc32(payload) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + payload + struct.pack('>I', crc)


def _write_png(path: str, width: int, height: int, rgb_data: bytes) -> None:
    row_bytes = width * 3
    scanlines = bytearray((row_bytes + 1) * height)
    for y in range(height):
        source_offset = y * row_bytes
        target_offset = y * (row_bytes + 1)
        scanlines[target_offset] = 0
        scanline_start = target_offset + 1
        scanlines[scanline_start : scanline_start + row_bytes] = rgb_data[
            source_offset : source_offset + row_bytes
        ]

    png_data = (
        b'\x89PNG\r\n\x1a\n'
        + _png_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b'IDAT', zlib.compress(scanlines))
        + _png_chunk(b'IEND', b'')
    )

    with open(path, 'wb') as f:
        f.write(png_data)


def _write_image(path: str, width: int, height: int, rgb_data: bytes) -> None:
    if path.lower().endswith('.ppm'):
        _write_ppm(path, width, height, rgb_data)
        return

    _write_png(path, width, height, rgb_data)


def _open_image(path: str) -> None:
    system = platform.system()
    try:
        if system == 'Darwin':
            subprocess.run(['open', '--', path], check=True)
        elif system == 'Windows':
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(['xdg-open', Path(path).resolve().as_uri()], check=True)
    except (AttributeError, FileNotFoundError, OSError, subprocess.CalledProcessError) as err:
        gdb.write(f'framebuffer_display: image saved, but opening it failed: {err}\nOpen manually: {path}\n')


def _read_memory(address: int, size: int) -> bytes:
    inferior = gdb.selected_inferior()
    if inferior is None:
        raise gdb.GdbError('no inferior is selected')
    return bytes(inferior.read_memory(address, size))


def _parse_args(arg: str) -> dict[str, OptionValue]:
    class _NoExitArgumentParser(argparse.ArgumentParser):
        def error(self, message: str) -> NoReturn:
            raise gdb.GdbError(message)

    try:
        argv = shlex.split(arg)
    except ValueError as err:
        raise gdb.GdbError(f'invalid command line: {err}') from err

    parser = _NoExitArgumentParser(add_help=False, prog='framebuffer_display')
    parser.add_argument('addr_pos', nargs='?')
    parser.add_argument('width_pos', nargs='?')
    parser.add_argument('height_pos', nargs='?')
    parser.add_argument('format_pos', nargs='?')
    parser.add_argument('-a', '--addr', dest='addr_opt')
    parser.add_argument('-e', '--expr', dest='expr_opt')
    parser.add_argument('-w', '--width', dest='width_opt', type=_parse_int)
    parser.add_argument('-h', '--height', dest='height_opt', type=_parse_int)
    parser.add_argument('-f', '--format', dest='format_opt')
    parser.add_argument('-s', '--stride', dest='stride', type=_parse_int)
    parser.add_argument('-o', '--output', dest='output')
    parser.add_argument('-c', '--crop', dest='crop')
    parser.add_argument('-n', '--no-show', dest='show', action='store_false', default=True)
    parser.add_argument('-?', '--help', dest='help', action='store_true')

    args = parser.parse_args(argv)
    opts: dict[str, OptionValue] = {}

    if args.help:
        opts['help'] = True
        return opts

    pos_values = (args.addr_pos, args.width_pos, args.height_pos, args.format_pos)
    has_positional = any(value is not None for value in pos_values)
    if has_positional and not all(value is not None for value in pos_values):
        raise gdb.GdbError('positional syntax expects: <expr/address> <width> <height> <format>')

    address_token = args.expr_opt or args.addr_opt or args.addr_pos
    if address_token is not None:
        opts['addr'] = _parse_address(address_token)

    width_token = args.width_opt if args.width_opt is not None else args.width_pos
    if width_token is not None:
        opts['width'] = width_token if isinstance(width_token, int) else _parse_int(width_token)

    height_token = args.height_opt if args.height_opt is not None else args.height_pos
    if height_token is not None:
        opts['height'] = height_token if isinstance(height_token, int) else _parse_int(height_token)

    format_token = args.format_opt if args.format_opt is not None else args.format_pos
    if format_token is not None:
        opts['format'] = format_token.lower()

    if args.stride is not None:
        opts['stride'] = args.stride
    if args.output is not None:
        opts['output'] = args.output
    if args.crop is not None:
        opts['crop'] = args.crop
    if args.show is False:
        opts['show'] = False

    return opts


def _usage() -> str:
    return (
        'Usage:\n'
        '  framebuffer_display <gdb-expression/address> <width> <height> <format> \\\n'
        '    [-s <bytes>] [-c <x,y,w,h>] [-o <path>] [-n]\n'
        '  framebuffer_display --expr <gdb-expression> --width <pixels> --height <pixels> \\\n'
        '    --format <rgb565|bgr565|rgb888|bgr888|argb8888|rgba8888|bgra8888> [--stride <bytes>] \\\n'
        '    [--crop <x,y,w,h>] [--output <path>] [--no-show]\n'
        '  framebuffer_display --addr <address> --width <pixels> --height <pixels> \\\n'
        '    --format <rgb565|bgr565|rgb888|bgr888|argb8888|rgba8888|bgra8888> [--stride <bytes>] \\\n'
        '    [--crop <x,y,w,h>] [--output <path>] [--no-show]\n'
    )


def _bytes_per_pixel(pix_fmt: str) -> int:
    if pix_fmt in {'rgb565', 'bgr565'}:
        return 2
    if pix_fmt in {'rgb888', 'bgr888'}:
        return 3
    return 4


def _parse_crop(crop_text: str, width: int, height: int) -> tuple[int, int, int, int]:
    parts = [item.strip() for item in crop_text.split(',')]
    if len(parts) != 4:
        raise gdb.GdbError('--crop expects x,y,w,h')

    try:
        crop_x, crop_y, crop_w, crop_h = (_parse_int(part) for part in parts)
    except ValueError as exc:
        raise gdb.GdbError('--crop expects x,y,w,h as integers') from exc
    if crop_w <= 0 or crop_h <= 0:
        raise gdb.GdbError('crop width and height must be positive')
    if crop_x < 0 or crop_y < 0:
        raise gdb.GdbError('crop x and y must be non-negative')
    if crop_x + crop_w > width or crop_y + crop_h > height:
        raise gdb.GdbError('crop rectangle exceeds framebuffer dimensions')

    return crop_x, crop_y, crop_w, crop_h


def _require_int(opts: dict[str, OptionValue], key: str) -> int:
    value = opts.get(key)
    if not isinstance(value, int):
        raise gdb.GdbError(f'invalid value for --{key}')
    return value


def _require_str(opts: dict[str, OptionValue], key: str) -> str:
    value = opts.get(key)
    if not isinstance(value, str):
        raise gdb.GdbError(f'invalid value for --{key}')
    return value


class FramebufferDisplayCommand(gdb.Command):
    """Dump framebuffer memory and open it with the system image viewer.

    Usage:
      framebuffer_display <gdb-expression/address> <width> <height> <format>
      [-s <bytes>] [-c <x,y,w,h>] [-o <path>] [-n]

    Required arguments:
      <gdb-expression/address>  Framebuffer base address or expression.
      <width>                   Framebuffer width in pixels.
      <height>                  Framebuffer height in pixels.
      <format>                  rgb565|bgr565|rgb888|bgr888|argb8888|rgba8888|bgra8888

    Optional arguments:
      -s, --stride <bytes>         Bytes per row. Default: width * bytes_per_pixel.
      -c, --crop <x,y,w,h>         Dump only a rectangular region.
      -o, --output <path>          Output image path. Default: a PNG file in the system temporary directory.
      -n, --no-show                Export only, do not open the image viewer.
      -h, --height <pixels>        Long-form syntax option.
      -w, --width <pixels>         Long-form syntax option.
      -f, --format <format>        Long-form syntax option.
      -a, --addr <address>         Long-form syntax option.
      -e, --expr <expression>      Long-form syntax option.

    Example:
      framebuffer_display 0x48005bc0 800 480 rgb565 -c 0,0,200,120
    """

    def __init__(self) -> None:
        super().__init__('framebuffer_display', gdb.COMMAND_DATA)

    def complete(self, text: str, word: str) -> list[str]:
        text = text or ''
        word = word or ''
        token = ''
        stripped = text.rstrip()
        if stripped and not text.endswith(' '):
            try:
                token = shlex.split(stripped)[-1]
            except ValueError:
                token = stripped.split()[-1]
        if not word:
            word = token

        option_candidates = [
            '--addr',
            '-a',
            '--expr',
            '-e',
            '--width',
            '-w',
            '--height',
            '-h',
            '--format',
            '-f',
            '--stride',
            '-s',
            '--crop',
            '-c',
            '--output',
            '-o',
            '--no-show',
            '-n',
            '--help',
            '-?',
        ]

        if token.startswith('--'):
            long_prefix = token[2:]
            return [opt[2:] for opt in option_candidates if opt.startswith('--') and opt[2:].startswith(long_prefix)]

        if token.startswith('-') and not token.startswith('--'):
            short_prefix = token[1:]
            return [
                opt[1:]
                for opt in option_candidates
                if opt.startswith('-') and not opt.startswith('--') and opt[1:].startswith(short_prefix)
            ]

        if word.startswith('-'):
            return [opt for opt in option_candidates if opt.startswith(word)]

        try:
            tokens = shlex.split(text)
        except ValueError:
            tokens = []
        if tokens and tokens[-1] in {'--format', '-f'}:
            return [fmt for fmt in sorted(SUPPORTED_FORMATS) if fmt.startswith(word)]

        return []

    def invoke(self, arg: str, from_tty: bool) -> None:
        del from_tty
        opts = _parse_args(arg)
        if opts.get('help'):
            gdb.write(_usage())
            return

        for key in ('addr', 'width', 'height', 'format'):
            if key not in opts:
                raise gdb.GdbError(f'missing required argument: --{key}')

        pix_fmt = _require_str(opts, 'format')
        if pix_fmt not in SUPPORTED_FORMATS:
            raise gdb.GdbError(f'unsupported format: {pix_fmt}')

        width = _require_int(opts, 'width')
        height = _require_int(opts, 'height')
        if width <= 0 or height <= 0:
            raise gdb.GdbError('width and height must be positive')

        bytes_per_pixel = _bytes_per_pixel(pix_fmt)
        stride_opt = opts.get('stride')
        if stride_opt is None:
            stride = width * bytes_per_pixel
        else:
            if not isinstance(stride_opt, int):
                raise gdb.GdbError('invalid value for --stride')
            stride = stride_opt
        crop_x = 0
        crop_y = 0
        crop_w = width
        crop_h = height
        if 'crop' in opts:
            crop_x, crop_y, crop_w, crop_h = _parse_crop(_require_str(opts, 'crop'), width, height)
        read_size = stride * crop_h
        if read_size <= 0:
            raise gdb.GdbError('invalid read size')

        if 'output' in opts:
            output_path = _require_str(opts, 'output')
        else:
            output_path = os.path.join(tempfile.gettempdir(), 'framebuffer_display.png')

        addr = _require_int(opts, 'addr') + crop_y * stride
        raw = _read_memory(addr, read_size)
        rgb_data = _to_rgb_bytes(raw, crop_w, crop_h, stride, pix_fmt, x_offset=crop_x)
        _write_image(output_path, crop_w, crop_h, rgb_data)
        gdb.write(f'framebuffer_display: wrote {output_path}\n')

        if bool(opts.get('show', True)):
            _open_image(output_path)

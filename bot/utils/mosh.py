import os
import asyncio
import logging
import struct

logger = logging.getLogger(__name__)


def _process_avi_bytes(vid1_avi: str, combined_avi: str, output_avi: str):
    def get_00dc_offsets(data: bytes | bytearray) -> list[int]:
        movi_idx = data.find(b'movi')
        if movi_idx == -1: return []

        c_idx1 = data.find(b'idx1', movi_idx)
        if c_idx1 == -1: 
            c_idx1 = len(data)

        offsets = []
        search_idx = movi_idx + 4

        while search_idx < c_idx1:
            if search_idx + 8 > len(data):
                break

            chunk_id = data[search_idx : search_idx + 4]
            if chunk_id == b'00dc':
                offsets.append(search_idx)

            chunk_size = struct.unpack('<I', data[search_idx + 4 : search_idx + 8])[0]
            padding = chunk_size % 2 

            search_idx += 8 + chunk_size + padding

        return offsets

    with open(vid1_avi, 'rb') as f1:
        vid1_data = f1.read()

    vid1_offsets = get_00dc_offsets(vid1_data)
    vid1_frames_count = len(vid1_offsets)

    if vid1_frames_count == 0:
        logger.error("Не найдено кадров в первом видео.")
        return

    with open(combined_avi, 'rb') as fc:
        comb_data = bytearray(fc.read())

    offsets = get_00dc_offsets(comb_data)

    target_idx = vid1_frames_count

    if 0 < target_idx < len(offsets):
        prev_offset = offsets[target_idx - 1]
        prev_size = struct.unpack('<I', comb_data[prev_offset+4 : prev_offset+8])[0]
        prev_payload = comb_data[prev_offset+8 : prev_offset+8+prev_size]

        I_offset = offsets[target_idx]
        I_size = struct.unpack('<I', comb_data[I_offset+4 : I_offset+8])[0]

        if len(prev_payload) > I_size:
            new_payload = prev_payload[:I_size]
        else:
            new_payload = prev_payload + b'\x00' * (I_size - len(prev_payload))

        comb_data[I_offset+8 : I_offset+8+I_size] = new_payload

    with open(output_avi, 'wb') as out_file:
        out_file.write(comb_data)


async def async_mosh(vid1_path: str, vid2_path: str, concat_mp4: str, output_video: str, fps: int = 30):
    base = os.path.splitext(output_video)[0]
    vid1_avi = f"{base}_1.avi"
    vid2_avi = f"{base}_2.avi"
    list_txt = f"{base}_list.txt"
    combined_avi = f"{base}_combined.avi"
    moshed_avi = f"{base}_moshed.avi"
    audio_m4a = f"{base}_audio.m4a"

    try:
        video_filters = f'scale=720:1280,fps={fps},setsar=1'

        c1 = ['ffmpeg', '-y', '-loglevel', 'error', '-i', vid1_path,
              '-an', '-c:v', 'mpeg4', '-q:v', '2', '-bf', '0', '-g', '10000', '-sc_threshold', '0',
              '-vf', video_filters, vid1_avi]
        await (await asyncio.create_subprocess_exec(*c1)).communicate()

        c2 = ['ffmpeg', '-y', '-loglevel', 'error', '-i', vid2_path,
              '-an', '-c:v', 'mpeg4', '-q:v', '2', '-bf', '0', '-g', '10000', '-sc_threshold', '0',
              '-vf', video_filters, vid2_avi]
        await (await asyncio.create_subprocess_exec(*c2)).communicate()

        with open(list_txt, 'w', encoding='utf-8') as f:
            f.write(f"file '{os.path.abspath(vid1_avi)}'\n")
            f.write(f"file '{os.path.abspath(vid2_avi)}'\n")

        c3 = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
              '-i', list_txt, '-c', 'copy', combined_avi]
        await (await asyncio.create_subprocess_exec(*c3)).communicate()

        await asyncio.to_thread(_process_avi_bytes, vid1_avi, combined_avi, moshed_avi)

        has_audio = False
        c_audio = ['ffmpeg', '-y', '-loglevel', 'error', '-i', concat_mp4,
                   '-vn', '-c:a', 'copy', audio_m4a]
        await (await asyncio.create_subprocess_exec(*c_audio)).communicate()

        if os.path.exists(audio_m4a) and os.path.getsize(audio_m4a) > 100:
            has_audio = True

        cmd_out = ['ffmpeg', '-y', '-loglevel', 'error', '-i', moshed_avi]

        if has_audio:
            cmd_out.extend(['-i', audio_m4a])

        cmd_out.extend([
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-pix_fmt', 'yuv420p'
        ])

        if has_audio:
            cmd_out.extend(['-c:a', 'aac', '-b:a', '128k', '-shortest'])

        cmd_out.append(output_video)

        await (await asyncio.create_subprocess_exec(*cmd_out)).communicate()

    finally:
        for p in [vid1_avi, vid2_avi, list_txt, combined_avi, moshed_avi, audio_m4a]:
            if os.path.exists(p):
                os.remove(p)

"""Prepare indexes of unchanged H.264 packets; never transcode or download implicitly."""
import base64
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

from .web import _canonical, _sha, MAX_FILE_BYTES


def index_film(source, output):
    source, output = Path(source), Path(output)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('An existing bounded native film is required')
    digest = _sha(source)
    generator = _sha(Path(__file__))
    if output.exists() or output.is_symlink():
        if output.is_symlink() or not output.is_file():
            raise ValueError('The existing film index is not a regular file')
        index = json.loads(output.read_text())
        if index.get('sha256') != digest or index.get('generator_sha256') != generator:
            raise ValueError('Existing film index belongs to different source bytes or generator')
    else:
        ffprobe = shutil.which('ffprobe')
        if not ffprobe:
            raise ValueError('ffprobe is unavailable; unchanged-film packet preparation is blocked')
        with tempfile.TemporaryFile() as stream:
            try:
                completed = subprocess.run([ffprobe,'-v','error','-select_streams','v:0',
                    '-show_packets','-show_streams','-show_data','-show_entries',
                    'stream=codec_name,width,height,extradata,duration:packet=pts_time,duration_time,pos,size,flags',
                    '-of','json',str(source.resolve())],stdout=stream,stderr=subprocess.PIPE,timeout=60)
            except subprocess.TimeoutExpired as error:
                raise ValueError('Film indexing exceeded its bounded preparation time') from error
            if completed.returncode or stream.tell() > 8*1024*1024:
                raise ValueError('Film cannot be indexed within the packet budget')
            stream.seek(0)
            probe = json.load(stream)
        tracks = probe.get('streams',[])
        if not tracks or tracks[0].get('codec_name') != 'h264':
            raise ValueError('This decoder requires unchanged H.264; use native playback or an explicit media adaptation')
        track = tracks[0]
        description = bytes.fromhex(''.join(line.split(':',1)[1].split('  ')[0].replace(' ','')
            for line in track.get('extradata','').splitlines() if ':' in line))
        duration = float(track['duration'])
        if len(description) < 4 or not math.isfinite(duration) or duration <= 0:
            raise ValueError('Missing usable native film configuration')
        packets = []
        for packet in probe.get('packets',[]):
            row = [int(packet['pos']),int(packet['size']),round(float(packet['pts_time'])*1e6),
                   round(float(packet['duration_time'])*1e6),int('K' in packet['flags'])]
            if row[0] < 0 or row[1] <= 0 or row[0]+row[1] > source.stat().st_size or row[3] <= 0:
                raise ValueError('Invalid native film packet range or timing')
            packets.append(row)
        if not packets or not packets[0][4] or len(packets) > 100000:
            raise ValueError('Missing keyframe or excessive packet index')
        index = {'version':1,'sha256':digest,'source_size_bytes':source.stat().st_size,
            'generator_sha256':generator,'codec':'avc1.'+description[1:4].hex(),
            'width':int(track['width']),'height':int(track['height']),'duration':duration,
            'description':base64.b64encode(description).decode(),'packets':packets}
        if _sha(source) != digest:
            raise ValueError('Film changed during packet preparation')
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('xb') as stream:
            stream.write(_canonical(index))
    return {'status':'PASS','scope':'unchanged_h264_packets_only','creative_quality':'NOT_ASSESSED',
            'source_sha256':digest,'index_sha256':_sha(output),'packets':len(index['packets']),
            'path':str(output)}

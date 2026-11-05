// Adapted from the pinned GProMer decoder. See PROVENANCE.json.
// Range reads are bounded. A server ignoring Range may serve a small complete
// file, but cannot silently allocate an entire large film for one packet.
export function createMediaReader(source,{maxBytes=8*1024*1024}={}) {
  let whole=null;
  return async (offset,size,signal)=>{
    if(!Number.isSafeInteger(offset)||offset<0||!Number.isSafeInteger(size)||size<=0||size>maxBytes)
      throw new RangeError('Invalid or excessive film byte range');
    if(whole) {
      if(offset+size>whole.byteLength)throw new RangeError('Film packet exceeds source');
      return whole.slice(offset,offset+size);
    }
    const response=await fetch(source,{headers:{Range:`bytes=${offset}-${offset+size-1}`},signal});
    if(!response.ok)throw new Error('Film range request failed');
    const declared=Number(response.headers.get('content-length'));
    if(Number.isFinite(declared)&&declared>maxBytes)throw new RangeError('Film response exceeds buffer budget');
    const reader=response.body.getReader(),parts=[];let length=0;
    try {
      for(;;) {
        const {value,done}=await reader.read();if(done)break;
        length+=value.byteLength;
        if(length>maxBytes)throw new RangeError('Film response exceeds buffer budget');
        parts.push(value);
      }
    } finally {await reader.cancel();}
    const bytes=new Uint8Array(length);let cursor=0;
    for(const part of parts){bytes.set(part,cursor);cursor+=part.byteLength;}
    if(response.status===206) {
      if(response.headers.get('content-range')?.split('/')[0]!==`bytes ${offset}-${offset+size-1}`||length!==size)
        throw new Error('Film byte range did not match request');
      return bytes;
    }
    if(response.status!==200||offset+size>length)throw new Error('Incomplete film response');
    whole=bytes;
    return whole.slice(offset,offset+size);
  };
}

// Decode short windows from the original MP4 ahead of scroll. The DOM scroll
// clock owns presentation; the HTML video seek/play clock never owns the canvas.
// At most 24 decoded HD surfaces across ALL scenes. Draw VideoFrame directly:
// copying every surface to ImageBitmap can add GPU/memory pressure on
// the same thread that must respond to the finger. Offscreen scenes close all.
const pool = new Set();
const activePlayers = new Set();
function retain(release) {
  pool.add(release);
  if (pool.size > 24) pool.values().next().value?.();
}

export async function createScrollFrames(
  source,
  signal,
  present,
  failed,
  read,
  {maxEncodedBytes=8*1024*1024}={},
) {
  if(!Number.isSafeInteger(maxEncodedBytes)||maxEncodedBytes<0||maxEncodedBytes>16*1024*1024)
    throw new RangeError('Invalid encoded-packet cache budget');
  if (
    typeof VideoDecoder === "undefined" ||
    typeof VideoFrame === "undefined"
  )
    return null;
  const response = await fetch(source + ".frames.json", { signal });
  if (!response.ok) return null;
  const index = await response.json();
  const config = {
    codec: index.codec,
    codedWidth: index.width,
    codedHeight: index.height,
    description: Uint8Array.from(atob(index.description), (c) =>
      c.charCodeAt(0),
    ),
  };
  if (!(await VideoDecoder.isConfigSupported(config)).supported) return null;
  signal.throwIfAborted();
  const times = index.packets.map((p) => p[2]).sort((a, b) => a - b);
  const ordinal = new Map(times.map((time, i) => [time, i]));
  const groups = [];
  for (const packet of index.packets) {
    if (packet[4]) groups.push({ packets: [], frames: [] });
    const group = groups.at(-1);
    group.packets.push(packet);
    group.frames.push(ordinal.get(packet[2]));
  }
  const cache = new Map();
  const encoded = new Map();
  let encodedBytes=0;
  const owner = {};
  let target = 0,
    direction = 1,
    active = false,
    disposed = false,
    generation = 0;
  let busy = false,
    decoder;
  let reading = false,
    pendingGroup,
    readAbort;
  let windowTarget = -1, windowDirection = 0, windowCount = 0;
  let desired = [];
  function frameWindow() {
    const count = Math.floor(24 / Math.max(1, activePlayers.size));
    if (windowTarget === target && windowDirection === direction && windowCount === count)
      return desired;
    windowTarget = target; windowDirection = direction; windowCount = count;
    if (count >= 24) {
      // A lone scene can use the existing pool for its current and next GOP.
      // Keeping complete decoded groups avoids decoding them again whenever a
      // sliding window advances by one frame. The global surface limit stays 24.
      const current = groups.findIndex(g => g.frames.includes(target));
      const frames = groups[current].frames;
      const inDirection = (a, b) => (a - b) * direction;
      desired = [
        target,
        ...frames.filter(i => (i - target) * direction > 0).sort(inDirection),
        ...(groups[current + direction]?.frames.slice().sort(inDirection) || []),
        ...frames.filter(i => (i - target) * direction < 0).sort((a, b) => inDirection(b, a)),
      ].slice(0, count);
    } else {
      const ahead = Math.ceil((count - 1) * 0.6);
      desired = [
        target,
        ...Array.from({ length: ahead }, (_, i) => target + direction * (i + 1)),
        ...Array.from({ length: count - 1 - ahead }, (_, i) => target - direction * (i + 1)),
      ];
    }
    return desired;
  }
  const wanted = (i) => frameWindow().includes(i);
  function show() {
    const hit = cache.get(target);
    if (active && hit) present(hit.picture);
  }
  function stop() {
    if (!active && !busy) return;
    activePlayers.delete(owner);
    active = false;
    generation++;
    busy = false;
    readAbort?.abort();
    readAbort = undefined;
    pendingGroup = undefined;
    reading = false;
    if (decoder?.state !== "closed") decoder?.close();
    decoder = undefined;
    for (const entry of [...cache.values()]) entry.release();
  }
  function fail() {
    if (disposed) return;
    destroy();
    failed();
  }
  function destroy() {
    disposed=true;stop();encoded.clear();encodedBytes=0;
    signal.removeEventListener('abort',destroy);
  }
  signal.addEventListener('abort',destroy,{once:true});
  async function pump() {
    if (!active || disposed || busy) return;
    const missing = frameWindow().find(
      (i) => i >= 0 && i < times.length && !cache.has(i),
    );
    if (missing === undefined) return;
    const group = groups.find((g) => g.frames.includes(missing));
    if (!group) return fail();
    busy = true;
    const version = generation;
    const packetRead = new AbortController();
    readAbort = packetRead;
    pendingGroup = group;
    try {
      if (!decoder || decoder.state === "closed")
        decoder = new VideoDecoder({
          output(frame) {
            const i = ordinal.get(frame.timestamp);
            if (
              version !== generation ||
              disposed ||
              !active ||
              i === undefined ||
              !wanted(i) ||
              cache.has(i)
            ) {
              frame.close();
              return;
            }
            const release = () => {
              frame.close();
              cache.delete(i);
              pool.delete(release);
            };
            cache.set(i, {
              picture: { image: frame, time: times[i] / 1e6 }, release,
            });
            retain(release);
            show();
          },
          error: fail,
        });
      // A fresh output closure belongs to one batch/generation. Flush drains
      // reordered B-frames; close frees hardware surfaces before the next batch.
      decoder.configure(config);
      const batch = decoder;
      for (const [offset, size, timestamp, duration, key] of group.packets) {
        let chunk = encoded.get(offset);
        if (!chunk) {
          reading = true;
          const packet = await read(offset, size, packetRead.signal);
          if (version !== generation || disposed || !active) return;
          reading = false;
          chunk = new EncodedVideoChunk({
            type: key ? "key" : "delta",
            timestamp,
            duration,
            data: packet,
          });
          if(chunk.byteLength<=maxEncodedBytes) {
            while(encodedBytes+chunk.byteLength>maxEncodedBytes) {
              const oldest=encoded.keys().next().value;
              encodedBytes-=encoded.get(oldest).byteLength;encoded.delete(oldest);
            }
            encoded.set(offset,chunk);encodedBytes+=chunk.byteLength;
          }
        }
        if (version !== generation || disposed || !active) return;
        batch.decode(chunk);
        // Yield between queued packets rather than feeding a whole GOP in one
        // input task. The original decode/presentation timestamps stay intact.
        if (batch.decodeQueueSize >= 4)
          await new Promise(resolve => setTimeout(resolve, 0));
      }
      if (version !== generation || disposed || !active) return;
      await batch.flush();
      if (version !== generation || disposed) return;
      batch.close();
      decoder = undefined;
      busy = false;
      readAbort = undefined;
      pendingGroup = undefined;
      for (const [i, entry] of cache) if (!wanted(i)) entry.release();
      show();
      void pump();
    } catch {
      if (version === generation && !disposed) fail();
    }
  }
  return {
    duration: index.duration,
    get stats(){return {encodedBytes,decodedFrames:cache.size,disposed};},
    seek(time) {
      if (disposed) return;
      const next = Math.max(
        0,
        Math.min(
          times.length - 1,
          Math.round((time * times.length) / index.duration),
        ),
      );
      if (next !== target) direction = Math.sign(next - target);
      target = next;
      // A future byte range must never hold a reversal hostage. Cancel only a
      // pending network read outside the newly requested GOP; ready decode work
      // continues normally and downloaded/encoded packets remain reusable.
      if (reading && pendingGroup && !pendingGroup.frames.includes(next) && !cache.has(next)) {
        generation++;
        readAbort?.abort();
        readAbort = undefined;
        pendingGroup = undefined;
        reading = false;
        busy = false;
        if (decoder?.state !== "closed") decoder?.close();
        decoder = undefined;
      }
      active = true;
      activePlayers.add(owner);
      for (const [i, entry] of cache) if (!wanted(i)) entry.release();
      show();
      void pump();
    },
    suspend: stop,
    destroy,
  };
}

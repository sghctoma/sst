var m = require("mithril")
var Session = require("../models/Session")

function getMP4CreationTime(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataView = new DataView(reader.result);
      let pos = 0;
      while (pos < dataView.byteLength) {
        const boxSize = dataView.getUint32(pos);
        const boxType = String.fromCharCode(
          dataView.getUint8(pos + 4),
          dataView.getUint8(pos + 5),
          dataView.getUint8(pos + 6),
          dataView.getUint8(pos + 7)
        );
        if (boxType === "moov") {
          pos += 8;
          const mvhdSize = dataView.getUint32(pos);
          const mvhdType = String.fromCharCode(
            dataView.getUint8(pos + 4),
            dataView.getUint8(pos + 5),
            dataView.getUint8(pos + 6),
            dataView.getUint8(pos + 7)
          );
          if (mvhdType === "mvhd") {
            const version = dataView.getUint8(pos + 8)
            var creationTime = null
            if (version == 1) {
              creationTime = dataView.getUint32(pos + 12) * 4294967296 +
              dataView.getUint32(pos + 16) -
              2082844800;
            } else {
              creationTime = dataView.getUint32(pos + 12) - 2082844800;
            }
            resolve(creationTime);
          }
        } else {
          pos += boxSize;
          if (boxSize === 0) {
            break;
          }
        }
      }
      reject(new Error("Creation time not found"));
    };
    reader.readAsArrayBuffer(file);
  });
}

var waitForMetadata = async function() {
  return new Promise((resolve) => {
    const interval = setInterval(() => {
      if (!isNaN(VideoPlayer.video.duration)) {
        clearInterval(interval);
        resolve();
      }
    }, 10);
  });
}

var overlapsWithSession = function(creationTime) {
  const videoEndTime = creationTime + VideoPlayer.video.duration
  return (Session.current.start_time < videoEndTime &&
          creationTime < Session.current.end_time)
}

var Video = {
  oncreate: function(vnode) {
    vnode.dom.preload = 'metadata';
    VideoPlayer.video = vnode.dom
  },
  view: function(vnode) {
    return m("video", {
      class: VideoPlayer.loaded ? "video-loaded" : "video-empty",
      onseeking: (e) => {
        VideoPlayer.seeking = true
        e.redraw = false
      },
      onseeked: (e) => {
        VideoPlayer.seeking = false
        e.redraw = false
      },
      ontimeupdate: (e) => {
        if (!VideoPlayer.seeking) {
          VideoPlayer.travelSpan.location = vnode.dom.currentTime - VideoPlayer.timeOffset
        }
        e.redraw = false
      },
    })
  }
}

var VideoPlayer = {
  oninit: function(vnode) {
    VideoPlayer.loaded = false
    VideoPlayer.error = null
    VideoPlayer.video = null
    VideoPlayer.timeOffset = null
    VideoPlayer.seeking = false
  },
  onremove: function(vnode) {
    VideoPlayer.oninit(vnode)
  },
  seek: function(seconds) {
    if (!VideoPlayer.seeking && VideoPlayer.video.paused) {
      VideoPlayer.video.currentTime = VideoPlayer.timeOffset + seconds
    }
  },
  loadVideo: async function(file) {
    const type = file.type
    const canPlay = VideoPlayer.video.canPlayType(type)
    if (!canPlay) {
      VideoPlayer.error = "Can't play this video type"
      m.redraw()
      return
    }

    const fileURL = URL.createObjectURL(file)
    VideoPlayer.video.src = fileURL
    
    await waitForMetadata()
    const creationTime = await getMP4CreationTime(file)
    if (!overlapsWithSession(creationTime)) {
      VideoPlayer.error = "Video and session do not overlap"
      SST.setError(VideoPlayer.error)
      m.redraw()
      setTimeout(() => {
        VideoPlayer.error = ""
        m.redraw()
      }, 1500)
      return
    }
    
    VideoPlayer.timeOffset = Session.current.start_time - creationTime
    VideoPlayer.video.currentTime = VideoPlayer.timeOffset
    VideoPlayer.error = null
    VideoPlayer.loaded = true
    VideoPlayer.video.controls = true
    m.redraw()
  },
  view: function(vnode) {
    return !VideoPlayer.error ? m(Video) : null
  }
}

module.exports = VideoPlayer
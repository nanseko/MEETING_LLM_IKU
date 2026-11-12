const browsePath = document.getElementById("browse-path");
const recordingDir = document.getElementById("recording-dir");

browsePath.addEventListener("click", () => {
  recordingDir.focus();
  recordingDir.select();
});

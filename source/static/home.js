const form = document.getElementById("minutes-form");
const fileInput = document.getElementById("file");
const dropzone = document.getElementById("dropzone");
const selectedFile = document.getElementById("selected-file");
const startButton = document.getElementById("record-start");
const pauseButton = document.getElementById("record-pause");
const stopButton = document.getElementById("record-stop");
const generateButton = document.getElementById("generate-docx");
const statusText = document.getElementById("record-status");
const progressLog = document.getElementById("progress-log");
const meetingTitleInput = document.getElementById("meeting-title");
const participantCountInput = document.getElementById("participant-count");
const meetingLanguageSelect = document.getElementById("meeting-language");
const secureBusinessInput = document.getElementById("meeting-secure-business");
const meetingInfoSaveButton = document.getElementById("meeting-info-save");
const meetingInfoResetButton = document.getElementById("meeting-info-reset");
const meetingInfoStatus = document.getElementById("meeting-info-status");
const participantsList = document.getElementById("participants-list");
const participantAddButton = document.getElementById("participant-add");
const saveDocxButton = document.getElementById("save-docx");

const ACTIVE_JOB_KEY = "meetingMinutes.activeJobId";
const MEETING_INFO_KEY = "meetingMinutes.meetingInfo";

let mediaRecorder = null;
let mediaStream = null;
let recordedChunks = [];
let recordedBlob = null;
let recordedExtension = "webm";
let progressTimer = null;
let resumedJobId = null;
let pendingDownloadUrl = null;
let pendingCleanupUrl = null;

function participantRows() {
  return Array.from(participantsList.querySelectorAll(".participant-row"));
}

function renumberParticipants() {
  participantRows().forEach((row, index) => {
    row.querySelector(".participant-index").textContent = String(index + 1);
    row.querySelector(".participant-remove").disabled = participantRows().length <= 1;
  });
}

function createParticipantRow(data = {}) {
  const row = document.createElement("div");
  row.className = "participant-row";

  const index = document.createElement("div");
  index.className = "participant-index";

  const department = document.createElement("input");
  department.type = "text";
  department.placeholder = "부서명";
  department.dataset.field = "department";
  department.value = data.department || "";

  const position = document.createElement("input");
  position.type = "text";
  position.placeholder = "직급";
  position.dataset.field = "position";
  position.value = data.position || "";

  const name = document.createElement("input");
  name.type = "text";
  name.placeholder = "이름";
  name.dataset.field = "name";
  name.value = data.name || "";

  const remove = document.createElement("button");
  remove.className = "participant-remove";
  remove.type = "button";
  remove.textContent = "-";
  remove.setAttribute("aria-label", "참여 인원 삭제");
  remove.addEventListener("click", () => {
    if (participantRows().length <= 1) {
      return;
    }
    row.remove();
    renumberParticipants();
  });

  row.append(index, department, position, name, remove);
  participantsList.appendChild(row);
  renumberParticipants();
}

function renderParticipants(participants = []) {
  participantsList.innerHTML = "";

  const labels = document.createElement("div");
  labels.className = "participants-column-labels";
  for (const label of ["순번", "부서명", "직급", "이름", "삭제"]) {
    const item = document.createElement("span");
    item.textContent = label;
    labels.appendChild(item);
  }
  participantsList.appendChild(labels);

  const rows = participants.length ? participants : [{}];
  for (const participant of rows) {
    createParticipantRow(participant);
  }
}

function collectParticipants() {
  return participantRows()
    .map((row) => ({
      department: row.querySelector('[data-field="department"]').value.trim(),
      position: row.querySelector('[data-field="position"]').value.trim(),
      name: row.querySelector('[data-field="name"]').value.trim(),
    }))
    .filter((participant) => participant.department || participant.position || participant.name);
}

function setStatus(message, kind = "") {
  statusText.textContent = message;
  statusText.className = `status ${kind}`.trim();
}

function createJobId() {
  if (window.crypto && window.crypto.randomUUID) {
    return window.crypto.randomUUID().replace(/-/g, "");
  }
  return `${Date.now()}${Math.random().toString(16).slice(2)}`;
}

function saveActiveJob(jobId) {
  window.localStorage.setItem(ACTIVE_JOB_KEY, jobId);
}

function clearActiveJob(jobId) {
  if (!jobId || window.localStorage.getItem(ACTIVE_JOB_KEY) === jobId) {
    window.localStorage.removeItem(ACTIVE_JOB_KEY);
  }
}

function getActiveJob() {
  return window.localStorage.getItem(ACTIVE_JOB_KEY);
}

function loadMeetingInfo() {
  try {
    return JSON.parse(window.localStorage.getItem(MEETING_INFO_KEY) || "{}");
  } catch (_) {
    return {};
  }
}

function currentMeetingInfo() {
  return {
    meeting_title: meetingTitleInput.value.trim(),
    participants: collectParticipants(),
    participant_count: participantCountInput.value.trim(),
    meeting_language: meetingLanguageSelect.value || "ko",
    secure_business: secureBusinessInput.checked,
  };
}

function applyMeetingInfo(info) {
  meetingTitleInput.value = info.meeting_title || "";
  renderParticipants(Array.isArray(info.participants) ? info.participants : []);
  participantCountInput.value = info.participant_count || "";
  meetingLanguageSelect.value = info.meeting_language || "ko";
  if (Object.prototype.hasOwnProperty.call(info, "secure_business")) {
    secureBusinessInput.checked = Boolean(info.secure_business);
  }
}

function validateMeetingInfo(info) {
  if (info.participant_count) {
    const count = Number(info.participant_count);
    if (!Number.isInteger(count) || count < 1 || count > 99) {
      throw new Error("인원수는 1 이상 99 이하의 숫자만 입력할 수 있습니다.");
    }
  }
  if (!["ko", "en"].includes(info.meeting_language)) {
    throw new Error("사용언어를 다시 선택해 주세요.");
  }
}

function saveMeetingInfo() {
  const info = currentMeetingInfo();
  validateMeetingInfo(info);
  window.localStorage.setItem(MEETING_INFO_KEY, JSON.stringify(info));
  meetingInfoStatus.textContent = "회의 정보가 저장되었습니다.";
  meetingInfoStatus.className = "meeting-info-status ok";
  return info;
}

function resetMeetingInfo() {
  window.localStorage.removeItem(MEETING_INFO_KEY);
  meetingTitleInput.value = "";
  renderParticipants([]);
  participantCountInput.value = "";
  meetingLanguageSelect.value = "ko";
  secureBusinessInput.checked = false;
  meetingInfoStatus.textContent = "회의 정보를 다시 입력할 수 있습니다.";
  meetingInfoStatus.className = "meeting-info-status";
}

function savedMeetingInfoForSubmit() {
  const info = loadMeetingInfo();
  return {
    meeting_title: info.meeting_title || meetingTitleInput.value.trim(),
    participants: Array.isArray(info.participants) ? info.participants : collectParticipants(),
    participant_count: info.participant_count || participantCountInput.value.trim(),
    meeting_language: info.meeting_language || meetingLanguageSelect.value || "ko",
    secure_business: Object.prototype.hasOwnProperty.call(info, "secure_business")
      ? Boolean(info.secure_business)
      : secureBusinessInput.checked,
  };
}

function progressUrl(jobId) {
  const template = form.dataset.progressTemplate || `/progress/${jobId}`;
  return new URL(template.replace("__JOB_ID__", jobId), window.location.href).toString();
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function setBusyState(isBusy) {
  generateButton.disabled = isBusy;
  startButton.disabled = isBusy;
  pauseButton.disabled = true;
  stopButton.disabled = true;
  meetingInfoSaveButton.disabled = isBusy;
  meetingInfoResetButton.disabled = isBusy;
  participantAddButton.disabled = isBusy;
}

function renderProgress(events = []) {
  if (!progressLog) {
    return;
  }

  progressLog.innerHTML = "";
  if (!events.length) {
    const item = document.createElement("li");
    item.className = "muted";
    item.textContent = "아직 진행된 작업이 없습니다.";
    progressLog.appendChild(item);
    return;
  }

  for (const event of events) {
    const item = document.createElement("li");
    item.className = event.state || "running";
    const detail = event.detail ? ` (${event.detail})` : "";
    item.textContent = `[${event.time}] ${event.message}${detail}`;
    progressLog.appendChild(item);
  }
}

async function fetchProgress(jobId) {
  const response = await fetch(progressUrl(jobId), { cache: "no-store" });
  if (!response.ok) {
    throw new Error("진행 내역을 불러오지 못했습니다.");
  }
  return response.json();
}

async function refreshProgress(jobId) {
  const progress = await fetchProgress(jobId);
  const events = progress.events || [];
  renderProgress(events);

  const lastEvent = events.at(-1);
  if (lastEvent) {
    const kind = lastEvent.state === "error" ? "error" : lastEvent.state === "complete" ? "ok" : "";
    setStatus(lastEvent.message, kind);
  }

  return progress;
}

function startProgressPolling(jobId, { renderWaiting = true } = {}) {
  if (progressTimer) {
    clearInterval(progressTimer);
  }

  if (renderWaiting) {
    renderProgress([
      {
        time: new Date().toLocaleTimeString("ko-KR", { hour12: false }),
        message: "서버 작업 대기 중입니다.",
        state: "running",
      },
    ]);
  }

  progressTimer = setInterval(async () => {
    try {
      const progress = await refreshProgress(jobId);
      if (progress.state === "complete" || progress.state === "error" || progress.state === "idle") {
        clearInterval(progressTimer);
        progressTimer = null;
      }
    } catch (_) {
      // 작업 스레드가 막 시작되는 중일 수 있어 폴링을 유지한다.
    }
  }, 1200);
}

function stopProgressPolling() {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
}

async function waitForJob(jobId) {
  while (true) {
    const progress = await refreshProgress(jobId);
    if (progress.state === "complete" || progress.state === "error" || progress.state === "idle") {
      return progress;
    }
    await sleep(1200);
  }
}

function progressErrorMessage(progress) {
  if (progress.error) {
    return progress.error;
  }

  const events = progress.events || [];
  const lastEvent = events.at(-1);
  if (lastEvent && lastEvent.detail) {
    return lastEvent.detail;
  }
  if (lastEvent && lastEvent.message) {
    return lastEvent.message;
  }
  return "서버 처리 중 오류가 발생했습니다.";
}

function setFileList(files) {
  if (!files || files.length === 0) {
    return;
  }
  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(files[0]);
  fileInput.files = dataTransfer.files;
  recordedBlob = null;
  selectedFile.textContent = files[0].name;
  setStatus(`선택된 파일: ${files[0].name}`, "ok");
}

function getRecorderOptions() {
  const candidates = [
    { mimeType: "audio/webm;codecs=opus", extension: "webm" },
    { mimeType: "audio/webm", extension: "webm" },
    { mimeType: "audio/ogg;codecs=opus", extension: "ogg" },
    { mimeType: "audio/mp4", extension: "mp4" },
  ];

  for (const candidate of candidates) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported(candidate.mimeType)) {
      recordedExtension = candidate.extension;
      return { mimeType: candidate.mimeType };
    }
  }

  recordedExtension = "webm";
  return {};
}

function stopStream() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
  }
  mediaStream = null;
}

function resetRecording() {
  recordedChunks = [];
  recordedBlob = null;
  pauseButton.textContent = "일시정지";
}

function setRecordingControls(state) {
  const isRecording = state === "recording";
  const isPaused = state === "paused";
  const isStopping = state === "stopping";
  startButton.disabled = isRecording || isPaused || isStopping;
  pauseButton.disabled = !(isRecording || isPaused);
  stopButton.disabled = !(isRecording || isPaused);
  generateButton.disabled = isRecording || isPaused || isStopping;
}

dropzone.addEventListener("click", () => fileInput.click());

dropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropzone.classList.add("dragging");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("dragging");
});

dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("dragging");
  setFileList(event.dataTransfer.files);
});

fileInput.addEventListener("change", () => {
  setFileList(fileInput.files);
});

participantCountInput.addEventListener("input", () => {
  participantCountInput.value = participantCountInput.value.replace(/\D/g, "").slice(0, 2);
  if (Number(participantCountInput.value) > 99) {
    participantCountInput.value = "99";
  }
});

participantAddButton.addEventListener("click", () => {
  createParticipantRow();
});

meetingInfoSaveButton.addEventListener("click", () => {
  try {
    saveMeetingInfo();
  } catch (error) {
    meetingInfoStatus.textContent = error.message;
    meetingInfoStatus.className = "meeting-info-status error";
  }
});

meetingInfoResetButton.addEventListener("click", resetMeetingInfo);

startButton.addEventListener("click", async () => {
  if (!window.isSecureContext) {
    setStatus("마이크 녹음은 HTTPS 또는 localhost 주소에서만 사용할 수 있습니다.", "error");
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setStatus("브라우저에서 마이크 API를 사용할 수 없습니다. 마이크 권한을 확인해 주세요.", "error");
    return;
  }

  if (!window.MediaRecorder) {
    setStatus("현재 브라우저는 MediaRecorder 녹음을 지원하지 않습니다.", "error");
    return;
  }

  try {
    resetRecording();
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(mediaStream, getRecorderOptions());

    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    });

    mediaRecorder.addEventListener("stop", () => {
      const mimeType = mediaRecorder.mimeType || "audio/webm";
      recordedBlob = new Blob(recordedChunks, { type: mimeType });
      stopStream();
      setRecordingControls("stopped");
      fileInput.value = "";
      selectedFile.textContent = `녹음 완료 ${(recordedBlob.size / 1024 / 1024).toFixed(2)} MB`;
      setStatus(`녹음 완료: ${(recordedBlob.size / 1024 / 1024).toFixed(2)} MB`, "ok");
    });

    mediaRecorder.start(1000);
    setRecordingControls("recording");
    setStatus("녹음 중입니다.");
  } catch (error) {
    stopStream();
    setStatus(`마이크를 사용할 수 없습니다: ${error.message}`, "error");
  }
});

pauseButton.addEventListener("click", () => {
  if (!mediaRecorder) {
    return;
  }

  if (mediaRecorder.state === "recording") {
    mediaRecorder.pause();
    pauseButton.textContent = "다시 시작";
    setRecordingControls("paused");
    setStatus("녹음이 일시정지되었습니다.");
  } else if (mediaRecorder.state === "paused") {
    mediaRecorder.resume();
    pauseButton.textContent = "일시정지";
    setRecordingControls("recording");
    setStatus("녹음 중입니다.");
  }
});

stopButton.addEventListener("click", () => {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    setRecordingControls("stopping");
    mediaRecorder.stop();
    setStatus("녹음을 정리하는 중입니다.");
  }
});

function getDownloadFilename(response) {
  const disposition = response.headers.get("Content-Disposition") || "";
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) {
    return decodeURIComponent(utf8Match[1]);
  }

  const asciiMatch = disposition.match(/filename="?([^"]+)"?/i);
  return asciiMatch ? asciiMatch[1] : "meeting_minutes.docx";
}

async function cleanupSecureJob(cleanupUrl) {
  if (!cleanupUrl) {
    return;
  }
  await fetch(new URL(cleanupUrl, window.location.href).toString(), {
    method: "POST",
    cache: "no-store",
  });
}

async function downloadDocx(downloadUrl, cleanupUrl = null) {
  const response = await fetch(new URL(downloadUrl, window.location.href).toString(), { cache: "no-store" });
  const contentType = response.headers.get("Content-Type") || "";
  if (!response.ok || !contentType.includes("application/vnd.openxmlformats-officedocument.wordprocessingml.document")) {
    if (contentType.includes("application/json")) {
      const payload = await response.json();
      throw new Error(payload.error || "DOCX 다운로드 중 오류가 발생했습니다.");
    }
    throw new Error("서버가 DOCX 파일을 반환하지 않았습니다.");
  }

  const docxBlob = await response.blob();
  const defaultFilename = getDownloadFilename(response);

  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: defaultFilename,
        types: [
          {
            description: "Word 문서",
            accept: {
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
            },
          },
        ],
      });
      const writable = await handle.createWritable();
      await writable.write(docxBlob);
      await writable.close();
      await cleanupSecureJob(cleanupUrl);
      return;
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error("파일 저장이 취소되었습니다.");
      }
      // 지원은 되지만 정책상 차단되는 환경이면 기존 다운로드로 폴백한다.
    }
  }

  const objectUrl = URL.createObjectURL(docxBlob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = defaultFilename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
  await cleanupSecureJob(cleanupUrl);
}

function prepareDocxSave(downloadUrl, cleanupUrl) {
  pendingDownloadUrl = downloadUrl;
  pendingCleanupUrl = cleanupUrl || null;
  if (window.showSaveFilePicker) {
    saveDocxButton.classList.remove("hidden");
    saveDocxButton.disabled = false;
    setStatus("DOCX 생성이 완료되었습니다. DOCX 저장 버튼을 눌러 저장 위치와 파일명을 선택하세요.", "ok");
    return;
  }
  saveDocxButton.classList.add("hidden");
}

saveDocxButton.addEventListener("click", async () => {
  if (!pendingDownloadUrl) {
    return;
  }
  saveDocxButton.disabled = true;
  try {
    await downloadDocx(pendingDownloadUrl, pendingCleanupUrl);
    pendingDownloadUrl = null;
    pendingCleanupUrl = null;
    saveDocxButton.classList.add("hidden");
    setStatus("DOCX 저장이 완료되었습니다. 다음 회의록 생성을 계속 사용할 수 있습니다.", "ok");
  } catch (error) {
    saveDocxButton.disabled = false;
    setStatus(`DOCX 저장 실패: ${error.message}`, "error");
  }
});

async function finishJobWhenReady(jobId) {
  try {
    const finalProgress = await waitForJob(jobId);
    if (finalProgress.state === "idle") {
      clearActiveJob(jobId);
      setStatus("이전 작업 정보를 찾을 수 없습니다.", "error");
      return;
    }
    if (finalProgress.state === "error") {
      throw new Error(progressErrorMessage(finalProgress));
    }
    if (!finalProgress.download_url) {
      throw new Error("DOCX 다운로드 경로를 받지 못했습니다.");
    }

    if (window.showSaveFilePicker) {
      prepareDocxSave(finalProgress.download_url, finalProgress.cleanup_url);
    } else {
      await downloadDocx(finalProgress.download_url, finalProgress.cleanup_url);
      setStatus("DOCX 다운로드가 시작되었습니다. 변환 기록에도 저장되었습니다.", "ok");
    }
    clearActiveJob(jobId);
  } catch (error) {
    clearActiveJob(jobId);
    setStatus(`DOCX 생성 실패: ${error.message}`, "error");
  } finally {
    stopProgressPolling();
    setBusyState(false);
    resumedJobId = null;
  }
}

async function resumeActiveJob() {
  const jobId = getActiveJob();
  if (!jobId) {
    return;
  }

  resumedJobId = jobId;
  setBusyState(true);
  setStatus("이전 작업의 진행 내역을 다시 불러오는 중입니다.");

  try {
    const progress = await refreshProgress(jobId);
    if (progress.state === "idle") {
      clearActiveJob(jobId);
      setBusyState(false);
      resumedJobId = null;
      return;
    }

    startProgressPolling(jobId, { renderWaiting: false });
    await finishJobWhenReady(jobId);
  } catch (error) {
    clearActiveJob(jobId);
    setBusyState(false);
    resumedJobId = null;
    setStatus(`이전 작업을 불러오지 못했습니다: ${error.message}`, "error");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (resumedJobId) {
    setStatus("이미 진행 중인 작업이 있습니다. 완료 후 다시 시도해 주세요.", "error");
    return;
  }

  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    setStatus("녹음을 먼저 중지한 뒤 DOCX를 생성해 주세요.", "error");
    return;
  }
  if (mediaRecorder && recordedChunks.length > 0 && !recordedBlob) {
    setStatus("녹음 파일을 정리하는 중입니다. 중지 완료 후 다시 시도해 주세요.", "error");
    return;
  }

  let meetingInfo;
  try {
    meetingInfo = savedMeetingInfoForSubmit();
    validateMeetingInfo(meetingInfo);
  } catch (error) {
    setStatus(error.message, "error");
    return;
  }

  const formData = new FormData();
  const jobId = createJobId();
  formData.append("job_id", jobId);
  formData.append("meeting_title", meetingInfo.meeting_title);
  formData.append("participants_json", JSON.stringify(meetingInfo.participants || []));
  formData.append("participant_count", meetingInfo.participant_count);
  formData.append("meeting_language", meetingInfo.meeting_language);
  formData.append("secure_business", meetingInfo.secure_business ? "true" : "false");

  if (recordedBlob) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    formData.append("file", recordedBlob, `recording_${timestamp}.${recordedExtension}`);
  } else if (fileInput.files.length > 0) {
    formData.append("file", fileInput.files[0]);
  } else {
    setStatus("업로드할 음성 파일을 선택하거나 녹음을 완료해 주세요.", "error");
    return;
  }

  saveActiveJob(jobId);
  pendingDownloadUrl = null;
  pendingCleanupUrl = null;
  saveDocxButton.classList.add("hidden");
  setBusyState(true);
  setStatus("음성 전처리 및 DOCX 생성을 시작합니다.");
  startProgressPolling(jobId);

  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "fetch",
      },
    });

    const contentType = response.headers.get("Content-Type") || "";
    if (!response.ok || !contentType.includes("application/json")) {
      if (contentType.includes("application/json")) {
        const payload = await response.json();
        throw new Error(payload.error || "서버 처리 중 오류가 발생했습니다.");
      }
      throw new Error("서버가 작업 접수 응답을 반환하지 않았습니다.");
    }

    const accepted = await response.json();
    if (accepted.job_id && accepted.job_id !== jobId) {
      throw new Error("작업 ID가 일치하지 않습니다.");
    }

    await finishJobWhenReady(jobId);
  } catch (error) {
    clearActiveJob(jobId);
    try {
      await refreshProgress(jobId);
    } catch (_) {
      // 기본 오류 메시지가 더 유용하다.
    }
    setStatus(`DOCX 생성 실패: ${error.message}`, "error");
  } finally {
    stopProgressPolling();
    setBusyState(false);
  }
});

applyMeetingInfo(loadMeetingInfo());
resumeActiveJob();

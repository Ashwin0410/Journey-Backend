// js/journal.js
// UPDATED for Felix's new design system
// Populates Felix's pre-existing Timeline page elements
// CHANGE #9: Extended to support new Journal Entry screen (replaced Activity Library)
// FIX: Added wireJournalScreen() to wire the Journal screen's Save button
// FIX: Corrected selectors for Journal Entry screen to match index.html
// UPDATED: Removed "Started" activity entries from timeline - only show "Completed"
// CHANGE #1: Added typewriter journal with auto-save functionality
// CHANGE #2: Autosave on blur/page leave - removed save button
// CHANGE #4: Load and display last 5 entries above textarea
// FIX Issue #3: Changed save logic to CREATE NEW entries instead of updating existing
// FIX Issue #5: Updated timeline rendering to use Felix's t-section/t-item structure
// FIX Issue #6: Changed stats from Chills to Day Streak
// FIX Issue #6: Added support for header journal button navigation
// FIX Issue #7: Journal heading "What's on your mind today?" support
// FIX Issue #2 (Timeline): Added event listener for activity:completed to auto-add timeline entries
// FIX Issue #2 (Timeline): Added auto-refresh when Timeline screen becomes active
// FIX Issue #2 (Timeline): Added setupActivityCompletionListener for automatic timeline updates
// FIX Issues #1 & #4: Improved stats update to ensure UI refreshes immediately after activity completion
// ML VIDEO REFACTOR: Added video session entries to timeline
// =============================================================================
// V5 FIXES (January 2026 - Felix Bug Fixes):
// - FIX Issue #6: Backend now creates journal entry on activity completion
//   - Updated addActivityCompleteLandmark to check journal_entry_created flag
//   - If backend already created entry, just reload timeline (no duplicate)
//   - Falls back to frontend creation for backward compatibility
// =============================================================================
// V11 FIXES (January 2026 - Timeline Update Fixes):
// - FIX Issue #5: Enhanced timeline refresh to force DOM updates
// - FIX Issue #5: Added forceRefreshTimeline() for immediate refresh
// - FIX Issue #5: Added screen visibility observer for auto-refresh on tab switch
// - FIX Issue #5: Added refreshStatsFromAPI() for direct stats fetch
// - FIX Issue #5: Enhanced updateStats() to force DOM reflow
// - FIX Issue #5: Added debouncing to prevent excessive refreshes
// - FIX Issue #5: Dispatch custom events for cross-component communication
// =============================================================================

(function () {
  const { qs, qsa, apiFetch, showToast } = window.JourneyUI;
  const Auth = window.JourneyAuth;

  let cachedStats = null;
  let cachedTimeline = null;
  let pastExpanded = false;
  let currentUser = null;
  let currentTodaySummary = null;

  // Auto-save state for typewriter journal
  let autoSaveTimeout = null;
  let lastSavedContent = "";

  // Cache for previous entries
  let previousEntriesCache = [];

  // FIX Issue #2: Track if timeline screen observer is set up
  let timelineObserverSetup = false;
  
  // FIX Issues #1 & #4: Track if activity completion listener is set up
  let activityListenerSetup = false;

  // ML VIDEO REFACTOR: Track if video completion listener is set up
  let videoListenerSetup = false;

  // V11 FIX Issue #5: Debounce tracking for timeline refresh
  let timelineRefreshTimeout = null;
  let lastTimelineRefresh = 0;
  const TIMELINE_REFRESH_DEBOUNCE_MS = 500; // Minimum time between refreshes

  // V11 FIX Issue #5: Track if journal screen observer is set up
  let journalScreenObserverSetup = false;

  async function ensureUserHash(userHash) {
    if (userHash && String(userHash).trim() !== "") return userHash;
    try {
      const me = await Auth.fetchCurrentUser();
      const u = me?.user || me || {};
      return u.user_hash || "";
    } catch {
      return "";
    }
  }

  // -------------------- Helpers --------------------

  function formatDateLabel(dateStr) {
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const entryDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());
      
      const diffDays = Math.floor((today - entryDate) / (1000 * 60 * 60 * 24));
      
      if (diffDays === 0) return "TODAY";
      if (diffDays === 1) return "YESTERDAY";
      if (diffDays < 7) return d.toLocaleDateString(undefined, { weekday: "long" }).toUpperCase();
      
      return d.toLocaleDateString(undefined, {
        month: "long",
        day: "numeric",
      }).toUpperCase();
    } catch {
      return dateStr;
    }
  }

  function formatDateFull(dateStr) {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      });
    } catch {
      return dateStr;
    }
  }

  function formatTime(dateStr) {
    try {
      const d = new Date(dateStr);
      return d.toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      });
    } catch {
      return "";
    }
  }

  function groupEntriesByDate(entries) {
    const groups = {};
    entries.forEach(entry => {
      const dateKey = formatDateLabel(entry.date || entry.created_at);
      if (!groups[dateKey]) {
        groups[dateKey] = [];
      }
      groups[dateKey].push(entry);
    });
    return groups;
  }

  function getEntryTypeLabel(entryType, entry = null) {
    if (entryType === "activity" && entry) {
      const meta = entry.meta || {};
      const activityName = meta.activity_name || entry.activity_name || "";
      if (activityName) {
        return activityName;
      }
    }

    // ML VIDEO REFACTOR: Handle video entry type
    if (entryType === "video" && entry) {
      const meta = entry.meta || {};
      const videoName = meta.video_name || entry.video_name || "";
      if (videoName) {
        return videoName;
      }
    }

    const labels = {
      journal: "Note",
      reflection: "Daily Reflection",
      daily_reflection: "Daily Reflection",
      activity: "Activity",
      session: "Journey Session",
      milestone: "Milestone",
      insight: "Insight",
      mood: "Mood Check-in",
      therapy: "Therapy Session",
      chills: "Chills Moment",
      // ML VIDEO REFACTOR: New entry types
      video: "Video Experience",
      video_session: "Video Experience",
    };
    return labels[entryType] || entryType;
  }

  function getInsightLabel(entry) {
    if (entry.entry_type === "session") return "Session Insight";
    if (entry.entry_type === "therapy") return "Session Insight";
    if (entry.entry_type === "chills") return "✧ Chills Insight";
    // ML VIDEO REFACTOR: Video insight label
    if (entry.entry_type === "video" || entry.entry_type === "video_session") return "✧ Video Insight";
    if (entry.insight || entry.ai_insight) return "Your Note";
    return "Insight";
  }

  function formatTypewriterDate() {
    const now = new Date();
    return now.toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
    }).toUpperCase();
  }

  // -------------------- STATS (Felix's Design) --------------------
  // Populate Felix's pre-existing stat cards

  function updateStats(stats) {
    if (!stats) {
      console.log("[Journal] updateStats called with no stats");
      return;
    }
    
    console.log("[Journal] updateStats called with:", stats);
    cachedStats = stats;

    // V11 FIX Issue #5: Try multiple selectors for stat elements
    const streakSelectors = ["#stat-streak", ".stat-streak", "[data-stat='streak']"];
    const activitiesSelectors = ["#stat-activities", ".stat-activities", "[data-stat='activities']"];

    let streakEl = null;
    let activitiesEl = null;

    // Find streak element
    for (const selector of streakSelectors) {
      streakEl = qs(selector);
      if (streakEl) break;
    }

    // Find activities element
    for (const selector of activitiesSelectors) {
      activitiesEl = qs(selector);
      if (activitiesEl) break;
    }

    if (streakEl) {
      // FIX Issues #1 & #4: Handle all possible field names for day streak
      const dayStreak = stats.day_streak ?? stats.streak ?? stats.current_streak ?? 0;
      
      // V11 FIX Issue #5: Force DOM update by clearing first
      streakEl.textContent = "";
      // Force reflow
      void streakEl.offsetHeight;
      streakEl.textContent = dayStreak;
      
      // V11 FIX Issue #5: Also set data attribute for debugging
      streakEl.dataset.lastUpdate = new Date().toISOString();
      
      console.log("[Journal] Updated #stat-streak to:", dayStreak);
    } else {
      console.log("[Journal] #stat-streak element not found");
    }

    if (activitiesEl) {
      // FIX Issues #1 & #4: Handle all possible field names for activities count
      const totalActivities = stats.activities_completed ?? stats.total_activities ?? 0;
      
      // V11 FIX Issue #5: Force DOM update by clearing first
      activitiesEl.textContent = "";
      // Force reflow
      void activitiesEl.offsetHeight;
      activitiesEl.textContent = totalActivities;
      
      // V11 FIX Issue #5: Also set data attribute for debugging
      activitiesEl.dataset.lastUpdate = new Date().toISOString();
      
      console.log("[Journal] Updated #stat-activities to:", totalActivities);
    } else {
      console.log("[Journal] #stat-activities element not found");
    }

    // Also update today.js stats if available
    if (window.JourneyToday?.updateTimelineStats) {
      window.JourneyToday.updateTimelineStats(stats);
    }

    // V11 FIX Issue #5: Dispatch event for other components that might need stats
    window.dispatchEvent(new CustomEvent("journey:statsUpdated", {
      detail: { stats, timestamp: Date.now() }
    }));
  }

  // =============================================================================
  // V11 FIX Issue #5: Force refresh stats directly from API
  // =============================================================================
  async function refreshStatsFromAPI(userHash) {
    try {
      const hash = await ensureUserHash(userHash);
      if (!hash) {
        console.warn("[Journal] refreshStatsFromAPI: No user hash available");
        return null;
      }

      console.log("[Journal] Fetching fresh stats from API...");
      
      const params = new URLSearchParams();
      params.set("user_hash", hash);

      const data = await apiFetch(
        `/api/journey/journal/timeline?${params.toString()}`,
        { method: "GET" }
      );

      const stats = data.stats || { day_streak: 0, activities_completed: 0 };
      console.log("[Journal] Fresh stats from API:", stats);
      
      updateStats(stats);
      return stats;
    } catch (err) {
      console.error("[Journal] Failed to refresh stats from API", err);
      return null;
    }
  }

  // =============================================================================
  // V11 FIX Issue #5: Force timeline refresh with debouncing
  // =============================================================================
  async function forceRefreshTimeline(userHash) {
    const now = Date.now();
    
    // Debounce: Don't refresh if we just did
    if (now - lastTimelineRefresh < TIMELINE_REFRESH_DEBOUNCE_MS) {
      console.log("[Journal] forceRefreshTimeline debounced (too soon)");
      return;
    }
    
    // Clear any pending refresh
    if (timelineRefreshTimeout) {
      clearTimeout(timelineRefreshTimeout);
      timelineRefreshTimeout = null;
    }
    
    lastTimelineRefresh = now;
    console.log("[Journal] forceRefreshTimeline executing...");
    
    // Clear cache to force fresh data
    cachedTimeline = null;
    
    await loadTimeline(userHash);
  }

  // -------------------- TIMELINE ITEM (Felix's Design) --------------------

  function renderTimelineItem(entry) {
    const meta = entry.meta || {};
    const isJournal = entry.entry_type === "journal" || entry.entry_type === "reflection" || entry.entry_type === "daily_reflection";
    
    // ML VIDEO REFACTOR: Check if this is a video entry
    const isVideo = entry.entry_type === "video" || entry.entry_type === "video_session";
    
    // Determine display title
    let displayTitle = entry.title;
    if (!displayTitle || displayTitle === "Activity started" || displayTitle === "Activity completed") {
      if (entry.entry_type === "activity") {
        const activityName = meta.activity_name || entry.activity_name || "";
        displayTitle = activityName || "Activity";
      } else if (isVideo) {
        // ML VIDEO REFACTOR: Video title
        const videoName = meta.video_name || entry.video_name || "";
        displayTitle = videoName || "Video Experience";
      } else {
        displayTitle = getEntryTypeLabel(entry.entry_type, entry);
      }
    }

    // Build meta line
    let metaParts = [];
    
    if (entry.entry_type === "activity") {
      const category = meta.life_area || meta.category || "";
      const duration = meta.duration_minutes || entry.duration_minutes || "";
      if (category) metaParts.push(category);
      if (duration) metaParts.push(`${duration} min`);
      metaParts.push("Completed");
    } else if (entry.entry_type === "session" || entry.entry_type === "therapy") {
      const duration = meta.duration_minutes || entry.duration_minutes || "";
      if (duration) metaParts.push(`${duration} min`);
      metaParts.push("Completed");
    } else if (entry.entry_type === "chills") {
      const chillsCount = meta.chills_count || 0;
      if (chillsCount > 0) metaParts.push(`${chillsCount} moments`);
    } else if (isVideo) {
      // ML VIDEO REFACTOR: Video meta line
      const chillsCount = meta.chills_count || 0;
      const valueSelected = meta.value_selected || "";
      if (chillsCount > 0) metaParts.push(`${chillsCount} chills`);
      if (valueSelected) metaParts.push(valueSelected);
      metaParts.push("Watched");
    } else if (isJournal) {
      // For journal entries, show context if available
      const context = meta.during_activity || "";
      if (context) metaParts.push(`During ${context}`);
    }
    
    const metaText = metaParts.join(" · ");

    // Body/entry text for journals
    const bodyText = entry.body || "";
    const truncatedBody = bodyText.length > 120 ? bodyText.substring(0, 120) + "..." : bodyText;

    // Insight text
    const insightText = entry.insight || entry.ai_insight || entry.session_insight || "";
    
    // ML VIDEO REFACTOR: Action text for video entries
    const actionText = meta.action_today || "";

    // Use Felix's t-item structure
    // ML VIDEO REFACTOR: Add video class for styling
    return `
      <div class="t-item ${isJournal ? 'journal' : ''} ${isVideo ? 'video' : ''}">
        <h3>${displayTitle}</h3>
        ${metaText ? `<p>${metaText}</p>` : ''}
        ${isJournal && truncatedBody ? `<p class="entry">"${truncatedBody}"</p>` : ''}
        ${!isJournal && !isVideo && insightText ? `<p class="entry">"${insightText}"</p>` : ''}
        ${isVideo && actionText ? `<p class="entry action">→ ${actionText}</p>` : ''}
        ${isVideo && insightText ? `<p class="entry insight">"${insightText}"</p>` : ''}
      </div>
    `;
  }

  // -------------------- TIMELINE SECTION (Felix's Design) --------------------

  function renderTimelineSection(label, entries) {
    if (!entries || !entries.length) return "";
    
    const entriesHtml = entries.map(entry => renderTimelineItem(entry)).join("");
    
    // Use Felix's t-section structure
    return `
      <div class="t-section">
        <p class="t-date">${label.toUpperCase()}</p>
        ${entriesHtml}
      </div>
    `;
  }

  // -------------------- FILTER OUT STARTED ACTIVITIES --------------------

  function filterOutStartedActivities(entries) {
    if (!entries || !Array.isArray(entries)) return entries;
    return entries.filter(entry => {
      if (entry.entry_type !== "activity") return true;
      const meta = entry.meta || {};
      const isCompleted = entry.completed_at || meta.completed || entry.title === "Activity completed";
      const isStarted = entry.title === "Activity started" || (!isCompleted && (entry.started_at || entry.body?.startsWith("Started")));
      return !isStarted;
    });
  }

  // -------------------- LOAD TIMELINE (Felix's Design) --------------------
  // Renders into Felix's pre-existing #timeline-sections container

  async function loadTimeline(userHash) {
    console.log("[Journal] loadTimeline called with userHash:", userHash ? "present" : "none");
    
    const container = qs("#timeline-sections") || qs("#screen-journal");
    if (!container) {
      console.warn("[Journal] Timeline container not found");
      return;
    }

    // Show loading state
    container.innerHTML = `
      <div class="timeline-loading" style="text-align: center; padding: 40px; color: var(--text-3);">
        Loading your journey...
      </div>
    `;

    try {
      const hash = await ensureUserHash(userHash);
      if (!hash) throw new Error("missing user_hash");

      const params = new URLSearchParams();
      params.set("user_hash", hash);

      console.log("[Journal] Fetching timeline from API...");
      const data = await apiFetch(
        `/api/journey/journal/timeline?${params.toString()}`,
        { method: "GET" }
      );

      console.log("[Journal] Timeline API response received");
      cachedTimeline = data;

      // Filter out started activities (only show completed)
      const future = filterOutStartedActivities(data.future || data.upcoming || []);
      const today = filterOutStartedActivities(data.today || []);
      const past = filterOutStartedActivities(data.past || data.earlier || []);
      
      // FIX Issues #1 & #4: Always update stats from backend response
      const stats = data.stats || { day_streak: 0, activities_completed: 0 };
      console.log("[Journal] Stats from timeline API:", stats);
      updateStats(stats);

      // Check if empty
      if (!future.length && !today.length && !past.length) {
        container.innerHTML = `
          <div class="timeline-empty" style="text-align: center; padding: 60px 20px;">
            <p style="color: var(--text-2); margin-bottom: 8px;">No entries yet.</p>
            <p style="color: var(--text-3); font-size: 0.875rem;">Your reflections, activities, and milestones will appear here.</p>
          </div>
        `;
        return;
      }

      // Build timeline HTML
      let html = "";

      // Today section
      if (today.length > 0) {
        html += renderTimelineSection("TODAY", today);
      }

      // Upcoming section
      if (future.length > 0) {
        html += renderTimelineSection("UPCOMING", future);
      }

      // Past sections (grouped by date)
      if (past.length > 0) {
        const grouped = groupEntriesByDate(past);
        const dateLabels = Object.keys(grouped);
        
        dateLabels.forEach(dateLabel => {
          html += renderTimelineSection(dateLabel, grouped[dateLabel]);
        });
      }

      container.innerHTML = html;
      console.log("[Journal] Timeline rendered successfully");

    } catch (err) {
      console.error("[Journal] Failed to load timeline", err);
      container.innerHTML = `
        <div class="timeline-error" style="text-align: center; padding: 60px 20px;">
          <p style="color: var(--text-2); margin-bottom: 16px;">Could not load your journey.</p>
          <button class="btn btn-secondary btn-sm" id="journal-retry-btn">Try Again</button>
        </div>
      `;

      const retryBtn = qs("#journal-retry-btn", container);
      if (retryBtn) {
        retryBtn.addEventListener("click", () => loadTimeline(userHash));
      }
    }
  }

  // -------------------- TYPEWRITER JOURNAL --------------------

  async function loadPreviousEntries() {
    try {
      const userHash = await ensureUserHash("");
      if (!userHash) return [];

      const response = await apiFetch(
        `/api/journey/journal/timeline?user_hash=${encodeURIComponent(userHash)}`,
        { method: "GET" }
      );

      const allEntries = [
        ...(response.today || []),
        ...(response.past || response.earlier || [])
      ];

      const journalEntries = allEntries
        .filter(entry => 
          entry.entry_type === "journal" || 
          entry.entry_type === "reflection" || 
          entry.entry_type === "daily_reflection"
        )
        .slice(0, 5);

      previousEntriesCache = journalEntries;
      return journalEntries;
    } catch (err) {
      console.warn("[Journal] Could not load previous entries:", err);
      return [];
    }
  }

  function renderPreviousEntries(entries, container) {
    const entriesContainer = qs("#journal-previous-entries", container);
    const separator = qs("#journal-entry-separator", container);
    
    if (!entriesContainer) {
      console.log("[Journal] Previous entries container not found");
      return;
    }

    if (!entries || entries.length === 0) {
      entriesContainer.innerHTML = "";
      if (separator) separator.style.display = "none";
      return;
    }

    if (separator) separator.style.display = "block";

    const reversedEntries = [...entries].reverse();
    
    const entriesHtml = reversedEntries.map((entry, index) => {
      const body = entry.body || "";
      const displayBody = body.length > 200 ? body.substring(0, 200) + "..." : body;
      return `
        <div class="journal-previous-entry" data-entry-id="${entry.id || index}">
          ${displayBody}
        </div>
        ${index < reversedEntries.length - 1 ? '<div class="journal-entry-separator"></div>' : ''}
      `;
    }).join("");

    entriesContainer.innerHTML = entriesHtml;
  }

  async function createNewJournalEntry(body) {
    try {
      const userHash = await ensureUserHash("");
      if (!userHash) return null;

      const firstLine = body.split("\n")[0].substring(0, 50);
      const title = firstLine.length > 3 ? firstLine : "Journal Entry";

      const response = await apiFetch("/api/journey/journal", {
        method: "POST",
        body: JSON.stringify({
          user_hash: userHash,
          entry_type: "journal",
          title: title,
          body: body,
          meta: { 
            source: "typewriter_journal",
            created_at: new Date().toISOString()
          },
        }),
      });

      return { saved: true, id: response?.id };
    } catch (err) {
      console.error("[Journal] Failed to create new entry:", err);
      return null;
    }
  }

  function updateAutoSaveIndicator(status) {
    const indicator = qs("#journal-autosave-indicator");
    if (!indicator) return;

    const textEl = qs(".autosave-text", indicator) || indicator;
    indicator.classList.remove("saving", "saved", "visible");

    if (status === "saving") {
      textEl.textContent = "Saving...";
      indicator.classList.add("saving", "visible");
    } else if (status === "saved") {
      textEl.textContent = "Saved";
      indicator.classList.add("saved", "visible");
      setTimeout(() => {
        indicator.classList.remove("visible");
      }, 2000);
    } else if (status === "error") {
      textEl.textContent = "Could not save";
      indicator.classList.add("visible");
      setTimeout(() => {
        indicator.classList.remove("visible");
      }, 3000);
    }
  }

  async function saveAndAddToEntries(body, textarea, container) {
    if (!body || body.trim() === "") return false;
    
    const trimmedBody = body.trim();
    
    if (trimmedBody === lastSavedContent) {
      console.log("[Journal] Content same as last saved, skipping duplicate save");
      return false;
    }

    updateAutoSaveIndicator("saving");

    const result = await createNewJournalEntry(trimmedBody);

    if (result && result.saved) {
      lastSavedContent = trimmedBody;
      updateAutoSaveIndicator("saved");

      if (textarea) {
        textarea.value = "";
      }

      const entries = await loadPreviousEntries();
      renderPreviousEntries(entries, container);

      const userHash = await ensureUserHash("");
      if (userHash) {
        loadTimeline(userHash);
      }

      if (window.JourneyFeed?.reload) {
        window.JourneyFeed.reload();
      }

      return true;
    } else {
      updateAutoSaveIndicator("error");
      return false;
    }
  }

  function wireTypewriterJournal() {
    const screen = qs("#screen-explore");
    if (!screen) return;

    const textarea = qs("#journal-typewriter-textarea", screen);

    if (!textarea) {
      console.log("[Journal] Typewriter textarea not found");
      return;
    }

    if (textarea.dataset.typewriterWired) return;
    textarea.dataset.typewriterWired = "1";

    console.log("[Journal] Wiring typewriter journal");

    const loadExistingContent = async () => {
      const entries = await loadPreviousEntries();
      renderPreviousEntries(entries, screen);
      lastSavedContent = "";
      textarea.value = "";
    };

    loadExistingContent();

    // Watch for screen becoming active
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === "class") {
          const target = mutation.target;
          if (target.classList.contains("active") && target.id === "screen-explore") {
            loadExistingContent();
          }
        }
      });
    });

    observer.observe(screen, { attributes: true });

    // Auto-save indicator on typing
    textarea.addEventListener("input", () => {
      const currentContent = textarea.value.trim();
      if (autoSaveTimeout) {
        clearTimeout(autoSaveTimeout);
      }
      if (!currentContent) {
        return;
      }
      autoSaveTimeout = setTimeout(() => {
        updateAutoSaveIndicator("saving");
        setTimeout(() => {
          updateAutoSaveIndicator("saved");
        }, 500);
      }, 1500);
    });

    // Save on blur creates NEW entry
    textarea.addEventListener("blur", async () => {
      const currentContent = textarea.value.trim();
      if (currentContent && currentContent !== lastSavedContent) {
        await saveAndAddToEntries(currentContent, textarea, screen);
      }
    });

    // Save before page unload
    const handleBeforeUnload = async () => {
      const currentContent = textarea.value.trim();
      if (currentContent && currentContent !== lastSavedContent) {
        await createNewJournalEntry(currentContent);
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    // Save when navigating away via nav buttons
    const navItems = qsa(".nav-item");
    navItems.forEach((navItem) => {
      navItem.addEventListener("click", async () => {
        if (screen.classList.contains("active")) {
          const currentContent = textarea.value.trim();
          if (currentContent && currentContent !== lastSavedContent) {
            await saveAndAddToEntries(currentContent, textarea, screen);
          }
        }
      });
    });

    // Also handle journey nav button (center play button)
    const journeyNavBtn = qs("#nav-journey-btn");
    if (journeyNavBtn) {
      journeyNavBtn.addEventListener("click", async () => {
        if (screen.classList.contains("active")) {
          const currentContent = textarea.value.trim();
          if (currentContent && currentContent !== lastSavedContent) {
            await saveAndAddToEntries(currentContent, textarea, screen);
          }
        }
      });
    }

    // FIX Issue #6: Handle header journal button click (save content when leaving journal screen)
    const headerJournalBtn = qs("#header-journal-btn");
    if (headerJournalBtn) {
      headerJournalBtn.addEventListener("click", async () => {
        // If user is on a different screen and clicking to go to journal, no need to save
        // But if already on journal screen, this would be a toggle or refresh
        if (screen.classList.contains("active")) {
          const currentContent = textarea.value.trim();
          if (currentContent && currentContent !== lastSavedContent) {
            await saveAndAddToEntries(currentContent, textarea, screen);
          }
        }
      });
    }

    console.log("[Journal] Typewriter journal wired successfully");
  }

  // -------------------- WIRE JOURNAL SCREEN --------------------

  function wireJournalScreen() {
    const screen = qs("#screen-journal");
    if (!screen) return;

    // FIX Issue #2: Setup observer to auto-refresh timeline when screen becomes active
    if (!timelineObserverSetup) {
      timelineObserverSetup = true;
      
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.attributeName === "class") {
            const target = mutation.target;
            if (target.classList.contains("active") && target.id === "screen-journal") {
              console.log("[Journal] Timeline screen became active, refreshing...");
              const userHash = currentUser?.user_hash || window.__JourneyUser?.user_hash || "";
              if (userHash) {
                loadTimeline(userHash);
              }
            }
          }
        });
      });

      observer.observe(screen, { attributes: true });
      console.log("[Journal] Timeline screen observer set up");
    }

    // Settings button in timeline header is wired by main.js/ui.js
    // Nothing else to wire in Felix's Timeline screen design
    
    console.log("[Journal] Journal/Timeline screen ready");
  }

  // -------------------- WIRE JOURNAL ENTRY SCREEN --------------------

  function wireJournalEntryScreen() {
    const screen = qs("#screen-explore");
    if (!screen) {
      console.log("[Journal] #screen-explore not found");
      return;
    }

    console.log("[Journal] Wiring Journal Entry screen (#screen-explore)");
    wireTypewriterJournal();

    const textarea = qs("#journal-typewriter-textarea", screen) ||
                     qs("#journal-entry-input", screen) || 
                     qs(".reflection-textarea", screen) ||
                     qs("textarea", screen);
    
    const saveBtn = qs("#journal-entry-save", screen) ||
                    qs(".btn-primary", screen);

    if (!textarea) {
      console.log("[Journal] No textarea found in Journal Entry screen");
      return;
    }

    // FIX Issue #7: Update journal heading if needed
    updateJournalHeading(screen);

    // Save button (if present - typewriter uses autosave)
    if (saveBtn && !saveBtn.dataset.wired) {
      saveBtn.dataset.wired = "1";

      saveBtn.addEventListener("click", async () => {
        const val = (textarea.value || "").trim();
        if (!val) {
          showToast?.("Write something first.");
          return;
        }

        saveBtn.disabled = true;
        const originalText = saveBtn.textContent;
        saveBtn.textContent = "Saving...";

        try {
          const userHash = await ensureUserHash("");
          if (!userHash) {
            showToast?.("Please sign in to save entries.");
            saveBtn.disabled = false;
            saveBtn.textContent = originalText;
            return;
          }

          const firstLine = val.split("\n")[0].substring(0, 50);
          const title = firstLine.length > 3 ? firstLine : "Journal Entry";

          await apiFetch("/api/journey/journal", {
            method: "POST",
            body: JSON.stringify({
              user_hash: userHash,
              entry_type: "journal",
              title: title,
              body: val,
              meta: { source: "journal_entry_screen" },
            }),
          });

          textarea.value = "";
          showToast?.("Journal entry saved! ✓");

          loadTimeline(userHash);

          if (window.JourneyFeed?.reload) {
            window.JourneyFeed.reload();
          }
        } catch (err) {
          console.error("[Journal] Failed to save entry", err);
          showToast?.("Could not save entry. Please try again.");
        } finally {
          saveBtn.disabled = false;
          saveBtn.textContent = originalText;
        }
      });
    }

    // Wire prompt chips if present
    const promptChips = qsa(".prompt-chip", screen);
    promptChips.forEach((chip) => {
      if (chip.dataset.journalWired) return;
      chip.dataset.journalWired = "1";
      chip.addEventListener("click", () => {
        const prompt = chip.textContent.trim();
        const prompts = {
          "How I'm feeling": "Right now I'm feeling...",
          "Something I noticed": "Today I noticed...",
          "A small win": "A small win from today was...",
          "A challenge": "Something that felt hard was...",
          "Grateful for": "Today I'm grateful for...",
          "Looking forward to": "I'm looking forward to...",
        };
        textarea.value = prompts[prompt] || prompt + " ";
        textarea.focus();
      });
    });

    console.log("[Journal] Journal Entry screen wiring complete");
  }

  // FIX Issue #7: Update journal heading styling/content if needed
  function updateJournalHeading(screen) {
    if (!screen) screen = qs("#screen-explore");
    if (!screen) return;

    const heading = qs(".journal-mind-heading", screen);
    if (heading) {
      // Heading exists - CSS handles the styling
      // Just ensure it has the correct text if empty
      if (!heading.textContent.trim()) {
        heading.textContent = "What's on your mind today?";
      }
      console.log("[Journal] Journal heading found and ready");
    }
  }

  // -------------------- FIX Issue #2: ACTIVITY COMPLETION LISTENER --------------------
  // Listen for activity completion events and automatically add timeline entries

  function setupActivityCompletionListener() {
    // FIX Issues #1 & #4: Only set up once
    if (activityListenerSetup) {
      console.log("[Journal] Activity completion listener already set up");
      return;
    }
    activityListenerSetup = true;
    
    // Listen for activity:completed events from today.js
    window.addEventListener("activity:completed", async (evt) => {
      console.log("[Journal] activity:completed event received", evt.detail);
      
      const detail = evt.detail || {};
      const activityId = detail.activity_id || detail.activityId || detail.id;
      const activityData = detail.activity || detail;
      const userHash = detail.user_hash || currentUser?.user_hash || window.__JourneyUser?.user_hash || "";
      // V5 FIX Issue #6: Check if backend already created the journal entry
      const journalEntryCreated = detail.journal_entry_created || false;
      const journalEntryId = detail.journal_entry_id || null;
      
      if (activityId) {
        console.log("[Journal] Adding activity completion to timeline:", activityId, "journal_entry_created:", journalEntryCreated);
        await addActivityCompleteLandmark(activityId, userHash, activityData, journalEntryCreated, journalEntryId);
        
        // V11 FIX Issue #5: Also refresh stats directly after completion
        await refreshStatsFromAPI(userHash);
      }
    });

    // Also listen for a more generic completion event
    window.addEventListener("journey:activityCompleted", async (evt) => {
      console.log("[Journal] journey:activityCompleted event received", evt.detail);
      
      const detail = evt.detail || {};
      const activityId = detail.activity_id || detail.activityId || detail.id;
      const activityData = detail.activity || detail;
      const userHash = detail.user_hash || currentUser?.user_hash || window.__JourneyUser?.user_hash || "";
      // V5 FIX Issue #6: Check if backend already created the journal entry
      const journalEntryCreated = detail.journal_entry_created || false;
      const journalEntryId = detail.journal_entry_id || null;
      
      if (activityId) {
        console.log("[Journal] Adding activity completion to timeline:", activityId, "journal_entry_created:", journalEntryCreated);
        await addActivityCompleteLandmark(activityId, userHash, activityData, journalEntryCreated, journalEntryId);
        
        // V11 FIX Issue #5: Also refresh stats directly after completion
        await refreshStatsFromAPI(userHash);
      }
    });

    console.log("[Journal] Activity completion listeners set up");
  }

  // =============================================================================
  // V11 FIX Issue #5: Journal Screen Visibility Observer
  // Auto-refresh timeline when the Journal tab/screen becomes active
  // =============================================================================
  function setupJournalScreenObserver() {
    if (journalScreenObserverSetup) {
      console.log("[Journal] Journal screen observer already set up");
      return;
    }
    journalScreenObserverSetup = true;

    // Find the journal/timeline screen
    const journalScreen = qs("#screen-journal") || qs("#screen-timeline");
    if (!journalScreen) {
      console.log("[Journal] Journal screen not found for observer setup");
      return;
    }

    // Watch for screen becoming active (class change to include 'active')
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === "class") {
          const target = mutation.target;
          if (target.classList.contains("active")) {
            console.log("[Journal] Journal screen became active, refreshing timeline...");
            const userHash = currentUser?.user_hash || window.__JourneyUser?.user_hash || "";
            if (userHash) {
              // Use debounced refresh
              if (timelineRefreshTimeout) {
                clearTimeout(timelineRefreshTimeout);
              }
              timelineRefreshTimeout = setTimeout(() => {
                forceRefreshTimeline(userHash);
              }, 100);
            }
          }
        }
      });
    });

    observer.observe(journalScreen, { attributes: true });
    console.log("[Journal] Journal screen observer set up");
  }

  // =============================================================================
  // ML VIDEO REFACTOR: Video Session Listener and Landmark
  // =============================================================================

  function setupVideoCompletionListener() {
    if (videoListenerSetup) {
      console.log("[Journal] Video completion listener already set up");
      return;
    }
    videoListenerSetup = true;

    // Listen for post-video completion events
    window.addEventListener("journey:postVideoComplete", async (evt) => {
      console.log("[Journal] journey:postVideoComplete event received", evt.detail);
      
      const detail = evt.detail || {};
      const sessionId = detail.sessionId;
      const insightsText = detail.insightsText || "";
      const valueSelected = detail.valueSelected || "";
      const actionToday = detail.actionToday || "";
      const chillsCount = detail.chillsCount || 0;
      const userHash = currentUser?.user_hash || window.__JourneyUser?.user_hash || "";
      
      if (sessionId) {
        console.log("[Journal] Adding video session to timeline:", sessionId);
        await addVideoSessionLandmark({
          session_id: sessionId,
          insights_text: insightsText,
          value_selected: valueSelected,
          action_today: actionToday,
          chills_count: chillsCount,
        }, userHash);
      }
    });

    // Also listen for video completion without post-video form (if user closes early)
    window.addEventListener("journey:videoComplete", async (evt) => {
      // Only add if post-video form won't be shown
      // (post-video form will add its own entry)
      console.log("[Journal] journey:videoComplete event received (may be handled by post-video form)");
    });

    console.log("[Journal] Video completion listeners set up");
  }

  /**
   * Add a video session entry to the timeline
   * @param {Object} videoData - Video session data
   * @param {string} userHash - User hash
   */
  async function addVideoSessionLandmark(videoData, userHash) {
    try {
      const hash = await ensureUserHash(userHash);
      if (!hash) throw new Error("missing user_hash");

      // Get video name from current session if available
      let videoName = videoData.video_name || "";
      if (!videoName && window.JourneyJourney?.getCurrentSession) {
        const session = window.JourneyJourney.getCurrentSession();
        videoName = session?.video_name || "";
      }
      if (!videoName && window.JourneyToday?.getCurrentVideoSuggestion) {
        const suggestion = window.JourneyToday.getCurrentVideoSuggestion();
        videoName = suggestion?.video?.stimulus_name || "";
      }

      const hasChills = (videoData.chills_count || 0) > 0;
      const title = videoName || "Video Experience";
      const body = videoData.insights_text || 
        (hasChills ? `Felt ${videoData.chills_count} moments of chills` : "Watched a video");

      console.log("[Journal] Creating timeline entry for video session:", title);

      await apiFetch("/api/journey/journal", {
        method: "POST",
        body: JSON.stringify({
          user_hash: hash,
          entry_type: "video",
          body: body,
          title: title,
          insight: videoData.action_today || "",
          meta: {
            session_id: videoData.session_id,
            video_name: videoName,
            chills_count: videoData.chills_count || 0,
            value_selected: videoData.value_selected || "",
            action_today: videoData.action_today || "",
            insights_text: videoData.insights_text || "",
          },
        }),
      });

      console.log("[Journal] Video session timeline entry created, refreshing...");
      
      // Reload timeline
      await loadTimeline(hash);
      
      showToast?.("Video experience added to your timeline! ✓");
      
    } catch (err) {
      console.error("[Journal] Failed to add video session landmark", err);
    }
  }

  // =============================================================================

  // -------------------- ADD LANDMARKS --------------------

  async function addActivityLandmark(activityId, userHash, activityData = {}) {
    // Activity started - not creating timeline entry (only completed activities shown)
    console.log("[Journal] Activity started - not creating timeline entry");
    return;
  }

  async function addActivityCompleteLandmark(activityId, userHash, activityData = {}, journalEntryCreated = false, journalEntryId = null) {
    try {
      const hash = await ensureUserHash(userHash);
      if (!hash) throw new Error("missing user_hash");

      // =============================================================================
      // V5 FIX Issue #6: Check if backend already created the journal entry
      // If so, just reload the timeline - no need to create duplicate entry
      // =============================================================================
      if (journalEntryCreated) {
        console.log("[Journal] Backend already created journal entry (ID:", journalEntryId, "), just reloading timeline");
        
        // V11 FIX Issue #5: Use forceRefreshTimeline for immediate update
        await forceRefreshTimeline(hash);
        
        // Get activity name for toast
        let activityName = activityData.title || activityData.name || "";
        if (!activityName && activityId) {
          try {
            const activityInfo = await apiFetch(`/api/journey/activity/${activityId}`, { method: "GET" });
            if (activityInfo) {
              activityName = activityInfo.title || activityInfo.name || "";
            }
          } catch (e) {
            // Ignore fetch error
          }
        }
        activityName = activityName || `Activity #${activityId}`;
        
        showToast?.(`${activityName} added to your timeline! ✓`);
        
        // V11 FIX Issue #5: Dispatch event for cross-component communication
        window.dispatchEvent(new CustomEvent("journey:timelineUpdated", {
          detail: { 
            activityId, 
            activityName, 
            journalEntryId,
            source: "backend",
            timestamp: Date.now() 
          }
        }));
        
        return;
      }
      // =============================================================================

      let activityName = activityData.title || activityData.name || "";
      let lifeArea = activityData.life_area || activityData.category || "";
      let duration = activityData.duration_min || activityData.default_duration_min || "";

      // FIX Issue #8: Fetch activity details from the new GET /api/journey/activity/{id} endpoint
      if (!activityName && activityId) {
        try {
          const activityInfo = await apiFetch(`/api/journey/activity/${activityId}`, { method: "GET" });
          if (activityInfo) {
            activityName = activityInfo.title || activityInfo.name || "";
            lifeArea = lifeArea || activityInfo.life_area || "";
            // Backend returns default_duration_min, not duration_min
            duration = duration || activityInfo.default_duration_min || activityInfo.duration_min || "";
          }
        } catch (fetchErr) {
          console.warn("[Journal] Could not fetch activity details, using fallback", fetchErr);
        }
      }

      if (!activityName) {
        activityName = `Activity #${activityId}`;
      }

      console.log("[Journal] Creating timeline entry for completed activity (frontend fallback):", activityName);

      await apiFetch("/api/journey/journal", {
        method: "POST",
        body: JSON.stringify({
          user_hash: hash,
          entry_type: "activity",
          body: `Completed ${activityName}`,
          title: "Activity completed",
          meta: { 
            activity_id: activityId,
            activity_name: activityName,
            life_area: lifeArea,
            duration_minutes: duration,
            completed: true,
          },
        }),
      });

      console.log("[Journal] Timeline entry created, refreshing timeline and stats...");
      
      // V11 FIX Issue #5: Use forceRefreshTimeline for immediate update
      await forceRefreshTimeline(hash);
      
      // Also notify user
      showToast?.(`${activityName} added to your timeline! ✓`);
      
      // V11 FIX Issue #5: Dispatch event for cross-component communication
      window.dispatchEvent(new CustomEvent("journey:timelineUpdated", {
        detail: { 
          activityId, 
          activityName, 
          source: "frontend",
          timestamp: Date.now() 
        }
      }));
      
    } catch (err) {
      console.error("[Journal] Failed to add activity complete landmark", err);
      // Don't show error toast - might be duplicate or backend handles it
    }
  }

  async function addSessionLandmark(sessionData, userHash) {
    try {
      const hash = await ensureUserHash(userHash);
      if (!hash) throw new Error("missing user_hash");

      const hasChills = sessionData.chills_moments?.length > 0;
      
      await apiFetch("/api/journey/journal", {
        method: "POST",
        body: JSON.stringify({
          user_hash: hash,
          entry_type: hasChills ? "chills" : "session",
          body: sessionData.summary || "Completed a Journey session",
          title: sessionData.title || `Session ${sessionData.session_number || ""} — ${hasChills ? "Chills Moment" : "Journey Audio"}`,
          insight: sessionData.insight || sessionData.chills_insight || "",
          meta: {
            session_id: sessionData.session_id,
            session_number: sessionData.session_number,
            duration_minutes: Math.floor((sessionData.duration_seconds || 0) / 60),
            chills_count: sessionData.chills_moments?.length || 0,
            chills_times: sessionData.chills_moments || [],
          },
        }),
      });

      await loadTimeline(hash);
    } catch (err) {
      console.error("[Journal] Failed to add session landmark", err);
      showToast?.("Could not add session landmark.");
    }
  }

  async function addMilestoneLandmark(milestone, userHash) {
    try {
      const hash = await ensureUserHash(userHash);
      if (!hash) throw new Error("missing user_hash");

      await apiFetch("/api/journey/journal", {
        method: "POST",
        body: JSON.stringify({
          user_hash: hash,
          entry_type: "milestone",
          body: milestone.description || "",
          title: milestone.title || "Milestone reached!",
          meta: {
            milestone_type: milestone.type,
            value: milestone.value,
          },
        }),
      });

      await loadTimeline(hash);
    } catch (err) {
      console.error("[Journal] Failed to add milestone landmark", err);
      showToast?.("Could not add milestone.");
    }
  }

  async function addTherapySession(sessionData, userHash) {
    try {
      const hash = await ensureUserHash(userHash);
      if (!hash) throw new Error("missing user_hash");

      await apiFetch("/api/journey/journal", {
        method: "POST",
        body: JSON.stringify({
          user_hash: hash,
          entry_type: "therapy",
          title: "Therapy Session",
          body: sessionData.topic || "",
          insight: sessionData.insight || sessionData.session_insight || "",
          meta: {
            therapist: sessionData.therapist || "Dr. Evans",
            duration_minutes: sessionData.duration_minutes || 50,
            session_date: sessionData.date || new Date().toISOString(),
          },
        }),
      });

      await loadTimeline(hash);
    } catch (err) {
      console.error("[Journal] Failed to add therapy session", err);
      showToast?.("Could not add therapy session.");
    }
  }

  // -------------------- SET TODAY SUMMARY --------------------

  function setTodaySummary(summary) {
    currentTodaySummary = summary;
    
    // Update stats if available
    if (summary?.stats) {
      updateStats(summary.stats);
    }
  }

  // -------------------- INIT --------------------

  function init(user) {
    currentUser = user;
    const userHash = user?.user_hash || "";
    
    console.log("[Journal] Initializing with user:", userHash ? "present" : "none");
    
    // FIX Issues #1 & #4: Setup activity completion listeners early
    setupActivityCompletionListener();
    
    // ML VIDEO REFACTOR: Setup video completion listeners
    setupVideoCompletionListener();
    
    // V11 FIX Issue #5: Setup journal screen visibility observer
    setupJournalScreenObserver();
    
    // Wire screens
    wireJournalScreen();
    wireJournalEntryScreen();
    
    // Load timeline if we have a user
    if (userHash) {
      loadTimeline(userHash);
    }
  }

  // -------------------- EXPORTS --------------------

  window.JourneyJournal = {
    init,
    loadTimeline,
    addActivityLandmark,
    addActivityCompleteLandmark,
    addSessionLandmark,
    addMilestoneLandmark,
    addTherapySession,
    setTodaySummary,
    updateStats,
    getStats: () => cachedStats,
    getTimeline: () => cachedTimeline,
    wireJournalEntryScreen,
    wireJournalScreen,
    wireTypewriterJournal,
    loadPreviousEntries,
    updateJournalHeading,
    // FIX Issue #2: Export for manual triggering if needed
    setupActivityCompletionListener,
    // ML VIDEO REFACTOR: New exports
    setupVideoCompletionListener,
    addVideoSessionLandmark,
    // V11 FIX Issue #5: New exports for timeline refresh
    forceRefreshTimeline,
    refreshStatsFromAPI,
    setupJournalScreenObserver,
  };
})();

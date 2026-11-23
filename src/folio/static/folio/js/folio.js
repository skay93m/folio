/*
 * Folio minimal progressive-enhancement script.
 * Zero HTML template-literal strings or raw innerHTML assembly.
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var params = new URLSearchParams(window.location.search);
  var requestedTheme = params.get("theme");
  if (requestedTheme === "light" || requestedTheme === "dark") {
    root.dataset.bsTheme = requestedTheme;
  }
  if (!root.dataset.printMode) {
    root.dataset.printMode = "colour";
  }

  function updateStatusMessage(selector, message) {
    var el = document.querySelector(selector);
    if (el) {
      el.textContent = message;
    }
  }

  // 1. Theme toggle
  var themeToggle = document.querySelector("#theme-toggle");
  function syncThemeButton() {
    if (!themeToggle) return;
    var current = root.dataset.bsTheme === "dark" ? "dark" : "light";
    themeToggle.textContent = current === "light" ? "Dark theme" : "Light theme";
    themeToggle.setAttribute(
      "aria-label",
      "Switch to " + (current === "light" ? "dark" : "light") + " theme"
    );
  }
  if (themeToggle) {
    syncThemeButton();
    themeToggle.addEventListener("click", function () {
      var nextTheme = root.dataset.bsTheme === "dark" ? "light" : "dark";
      root.dataset.bsTheme = nextTheme;
      syncThemeButton();
      var nextUrl = new URL(window.location.href);
      if (nextUrl.searchParams.has("theme") || nextUrl.searchParams.has("page")) {
        nextUrl.searchParams.set("theme", nextTheme);
        window.history.replaceState(null, "", nextUrl.toString());
      }
      if (typeof window.folioDrawTrend === "function") {
        window.folioDrawTrend();
      }
      updateStatusMessage("#preview-state", nextTheme + " theme active");
    });
  }

  // 2. Print mode and print trigger
  var isPrinting = false;
  var printSelect = document.querySelector("#print-mode");
  if (printSelect) {
    printSelect.value = root.dataset.printMode || "colour";
    printSelect.addEventListener("change", function () {
      root.dataset.printMode = printSelect.value;
      updateStatusMessage("#preview-state", "Print mode: " + printSelect.value);
    });
  }
  document.querySelectorAll("[data-folio-print]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      window.print();
    });
  });

  // 3. Pattern picker
  var pagePicker = document.querySelector("#page-picker");
  if (pagePicker) {
    pagePicker.addEventListener("change", function () {
      var option = pagePicker.options[pagePicker.selectedIndex];
      var href = option ? option.getAttribute("data-href") : null;
      if (href) {
        window.location.href = href;
      }
    });
  }

  // 4. Dashboard chart and period toggle
  var dashboardDataEl = document.querySelector("#dashboard-data");
  var trendCanvas = document.querySelector("#trend");
  var periodSelect = document.querySelector("#period");
  if (dashboardDataEl && trendCanvas) {
    var dashboardPeriods = JSON.parse(dashboardDataEl.textContent || "{}");
    var activePeriodKey = periodSelect ? periodSelect.value : Object.keys(dashboardPeriods)[0];

    function renderDashboardMetrics() {
      var period = dashboardPeriods[activePeriodKey];
      if (!period) return;
      var cards = document.querySelectorAll("#metrics .metric-card");
      (period.metrics || []).forEach(function (metric, idx) {
        var card = cards[idx];
        if (!card) return;
        var labelEl = card.querySelector(".metric-label");
        var valEl = card.querySelector(".metric-value");
        var compEl = card.querySelector(".metric-comparison");
        if (labelEl) labelEl.textContent = metric.label;
        if (valEl) valEl.textContent = metric.value;
        if (compEl) compEl.textContent = metric.comparison;
      });
      var tbody = document.querySelector("#trend-table tbody");
      var rowTpl = document.querySelector("#trend-row-template");
      if (tbody && rowTpl) {
        while (tbody.firstChild) {
          tbody.removeChild(tbody.firstChild);
        }
        (period.labels || []).forEach(function (lbl, idx) {
          var clone = rowTpl.content.cloneNode(true);
          var cells = clone.querySelectorAll("td");
          if (cells[0]) cells[0].textContent = lbl;
          if (cells[1]) cells[1].textContent = String(period.completed[idx]);
          if (cells[2]) cells[2].textContent = String(period.arrived[idx]);
          tbody.appendChild(clone);
        });
      }
    }

    window.folioDrawTrend = function () {
      var data = dashboardPeriods[activePeriodKey];
      if (!data || !trendCanvas) return;
      var ctx = trendCanvas.getContext("2d");
      if (!ctx) return;
      var ratio = window.devicePixelRatio || 1;
      var width = trendCanvas.clientWidth || 500;
      var height = trendCanvas.clientHeight || 260;
      trendCanvas.width = width * ratio;
      trendCanvas.height = height * ratio;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

      var style = window.getComputedStyle(root);
      var allValues = (data.completed || []).concat(data.arrived || [0]);
      var maximum = Math.max(2, Math.ceil(Math.max.apply(null, allValues) / 2) * 2);
      var left = 28;
      var right = width - 20;
      var top = 22;
      var bottom = height - 38;
      var printMode = root.dataset.printMode || "colour";
      var monochrome = isPrinting && printMode !== "colour";
      var ink = isPrinting ? "#000000" : style.getPropertyValue("--sk-muted").trim();

      ctx.font = "11px IBM Plex Sans, sans-serif";
      ctx.fillStyle = ink;

      for (var tick = 0; tick <= 4; tick++) {
        var y = bottom - (tick * (bottom - top)) / 4;
        ctx.strokeStyle = isPrinting
          ? printMode === "black-white"
            ? "#000000"
            : "#999999"
          : style.getPropertyValue("--sk-border").trim();
        ctx.lineWidth = 1;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(right, y);
        ctx.stroke();
        ctx.fillText(String((maximum * tick) / 4), 1, y + 4);
      }

      var labels = data.labels || [];
      labels.forEach(function (label, index) {
        var denom = Math.max(1, labels.length - 1);
        var x = left + (index * (right - left)) / denom;
        ctx.textAlign = index === 0 ? "left" : index === labels.length - 1 ? "right" : "center";
        ctx.fillText(label, x, height - 12);
      });

      ["arrived", "completed"].forEach(function (key) {
        var dashed = key === "arrived";
        var colour = style.getPropertyValue(dashed ? "--sk-chart-blue" : "--sk-coral").trim();
        if (isPrinting) {
          colour = dashed ? "#2864B4" : "#FF4F40";
        }
        if (monochrome) {
          colour = printMode === "greyscale" && dashed ? "#666666" : "#000000";
        }
        ctx.strokeStyle = colour;
        ctx.fillStyle = colour;
        ctx.lineWidth = 2.5;
        ctx.setLineDash(dashed ? [8, 5] : []);
        ctx.beginPath();
        var series = data[key] || [];
        var denom = Math.max(1, labels.length - 1);
        var points = series.map(function (value, index) {
          return [
            left + (index * (right - left)) / denom,
            bottom - (value / maximum) * (bottom - top),
          ];
        });
        points.forEach(function (pt, idx) {
          if (idx === 0) ctx.moveTo(pt[0], pt[1]);
          else ctx.lineTo(pt[0], pt[1]);
        });
        ctx.stroke();
        ctx.setLineDash([]);
        points.forEach(function (pt) {
          if (dashed) {
            ctx.beginPath();
            ctx.arc(pt[0], pt[1], 3.5, 0, Math.PI * 2);
            ctx.stroke();
          } else {
            ctx.fillRect(pt[0] - 3, pt[1] - 3, 6, 6);
          }
        });
      });
    };

    if (periodSelect) {
      periodSelect.addEventListener("change", function () {
        activePeriodKey = periodSelect.value;
        renderDashboardMetrics();
        window.requestAnimationFrame(window.folioDrawTrend);
      });
    }
    window.addEventListener("resize", window.folioDrawTrend);
    window.addEventListener("beforeprint", function () {
      isPrinting = true;
      window.folioDrawTrend();
    });
    window.addEventListener("afterprint", function () {
      isPrinting = false;
      window.folioDrawTrend();
    });
    window.requestAnimationFrame(window.folioDrawTrend);
  }

  // 5. Reading TOC scroll spy and progress bar
  var readingTocLinks = Array.prototype.slice.call(
    document.querySelectorAll('.reading-toc a[href^="#"]')
  );
  if (readingTocLinks.length > 0 && "IntersectionObserver" in window) {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          readingTocLinks.forEach(function (link) {
            link.classList.toggle("active", link.hash === "#" + entry.target.id);
          });
        });
      },
      { rootMargin: "-5% 0px -65% 0px" }
    );
    document.querySelectorAll(".article section[id]").forEach(function (section) {
      observer.observe(section);
    });
  }
  var readingProgress = document.querySelector(".reading-progress");
  if (readingProgress) {
    var updateProgress = function () {
      var scrollable = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      readingProgress.style.width = String((100 * window.scrollY) / scrollable) + "%";
    };
    window.addEventListener("scroll", updateProgress);
  }

  // 6. Search index progressive enhancement
  var searchText = document.querySelector("#search-text");
  var filtersContainer = document.querySelector("#filters");
  var filterRowTemplate = document.querySelector("#filter-row-template");
  if (searchText && filtersContainer) {
    var activeMode = "Notes";
    var activeTab = document.querySelector('[data-search-mode][aria-pressed="true"]');
    if (activeTab) {
      activeMode = activeTab.getAttribute("data-search-mode") || "Notes";
    }

    function addFilterRow(field, value) {
      if (!filterRowTemplate) return;
      var clone = filterRowTemplate.content.cloneNode(true);
      var row = clone.querySelector(".filter-row");
      var fieldSelect = row.querySelector(".filter-field");
      var valueInput = row.querySelector(".filter-value");
      var removeBtn = row.querySelector(".filter-remove");
      if (fieldSelect && field) fieldSelect.value = field;
      if (valueInput && value) valueInput.value = value;
      if (removeBtn) {
        removeBtn.addEventListener("click", function () {
          row.remove();
          runSearchFilter();
        });
      }
      filtersContainer.appendChild(clone);
    }

    function runSearchFilter() {
      var query = searchText.value.trim().toLowerCase();
      var filterRows = Array.prototype.slice.call(filtersContainer.querySelectorAll(".filter-row"));
      var filters = filterRows.map(function (row) {
        return {
          field: row.querySelector(".filter-field").value,
          operator: row.querySelector(".filter-operator").value,
          value: row.querySelector(".filter-value").value.trim().toLowerCase(),
        };
      });
      var items = Array.prototype.slice.call(document.querySelectorAll("#search-results .search-result"));
      var visibleCount = 0;
      items.forEach(function (item) {
        var matchesMode = activeMode === "Notes";
        var title = (item.getAttribute("data-title") || "").toLowerCase();
        var excerpt = (item.getAttribute("data-text") || "").toLowerCase();
        var matchesQuery = !query || title.indexOf(query) !== -1 || excerpt.indexOf(query) !== -1;
        var matchesFilters = filters.every(function (f) {
          if (!f.value) return true;
          var candidate = (item.getAttribute("data-" + f.field) || "").toLowerCase();
          if (f.operator === "not") return candidate !== f.value;
          if (f.operator === "contains") return candidate.indexOf(f.value) !== -1;
          return candidate === f.value;
        });
        var visible = matchesMode && matchesQuery && matchesFilters;
        item.hidden = !visible;
        if (visible) visibleCount += 1;
      });
      updateStatusMessage(
        "#result-count",
        String(visibleCount) + " " + activeMode.toLowerCase() + " in this sample"
      );
      var emptyEl = document.querySelector("#search-empty");
      if (emptyEl) {
        emptyEl.hidden = visibleCount > 0;
      }
    }

    var addFilterBtn = document.querySelector("#add-filter");
    if (addFilterBtn) {
      addFilterBtn.addEventListener("click", function () {
        addFilterRow("type", "");
      });
    }
    var runSearchBtn = document.querySelector("#run-search");
    if (runSearchBtn) {
      runSearchBtn.addEventListener("click", runSearchFilter);
    }
    searchText.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        runSearchFilter();
      }
    });
    var clearSearchBtn = document.querySelector("#clear-search");
    if (clearSearchBtn) {
      clearSearchBtn.addEventListener("click", function () {
        searchText.value = "";
        while (filtersContainer.firstChild) {
          filtersContainer.removeChild(filtersContainer.firstChild);
        }
        runSearchFilter();
      });
    }
    document.querySelectorAll("[data-facet-field]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        addFilterRow(btn.getAttribute("data-facet-field"), btn.getAttribute("data-facet-value"));
        runSearchFilter();
      });
    });
    document.querySelectorAll("[data-search-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        activeMode = btn.getAttribute("data-search-mode") || "Notes";
        document.querySelectorAll("[data-search-mode]").forEach(function (tab) {
          tab.setAttribute("aria-pressed", String(tab === btn));
        });
        runSearchFilter();
      });
    });
  }

  // 7. Work with journal preview
  var journalText = document.querySelector("#journal-text");
  var journalList = document.querySelector("#journal-list");
  var journalTpl = document.querySelector("#journal-entry-template");
  if (journalText && journalList && journalTpl) {
    var currentScope = "work";
    var currentJournalView = "all";
    var scopeLabel = document.querySelector("#scope-label");
    var switchScopeBtn = document.querySelector("#switch-scope");
    var journalCue = document.querySelector("#journal-cue");
    var workScopeText = scopeLabel ? scopeLabel.getAttribute("data-work-label") || "[work/review]" : "[work/review]";
    var generalScopeText = scopeLabel ? scopeLabel.getAttribute("data-general-label") || "[general]" : "[general]";

    function refreshJournalView() {
      var entries = Array.prototype.slice.call(journalList.querySelectorAll(".journal-entry"));
      var workCount = 0;
      var visibleCount = 0;
      entries.forEach(function (entry) {
        var scope = entry.getAttribute("data-scope") || "work";
        if (scope === "work") workCount += 1;
        var show = currentJournalView === "all" || scope === "work";
        entry.hidden = !show;
        if (show) visibleCount += 1;
      });
      updateStatusMessage("#all-count", String(entries.length));
      updateStatusMessage("#work-count", String(workCount));
      var emptyNotice = document.querySelector("#journal-empty");
      if (emptyNotice) emptyNotice.hidden = visibleCount > 0;
    }

    if (switchScopeBtn && scopeLabel) {
      switchScopeBtn.addEventListener("click", function () {
        currentScope = currentScope === "work" ? "general" : "work";
        scopeLabel.textContent = currentScope === "work" ? workScopeText : generalScopeText;
        switchScopeBtn.textContent =
          currentScope === "work" ? "Switch to General" : "Switch to This work";
      });
    }

    function addJournalCard() {
      var value = journalText.value.trim();
      if (!value) {
        updateStatusMessage("#journal-feedback", "Write a reflection before adding it.");
        journalText.focus();
        return;
      }
      var clone = journalTpl.content.cloneNode(true);
      var item = clone.querySelector(".journal-entry");
      var meta = clone.querySelector(".meta");
      var body = clone.querySelector(".journal-entry-body");
      var cueValue = journalCue ? journalCue.value.trim() : "";
      item.setAttribute("data-scope", currentScope);
      meta.textContent = (currentScope === "work" ? "This work" : "General") + (cueValue ? " · " + cueValue : "");
      body.textContent = journalText.value;
      journalList.insertBefore(clone, journalList.firstChild);
      journalText.value = "";
      if (journalCue) journalCue.value = "";
      updateStatusMessage("#journal-feedback", "Added to this preview. Memory only.");
      refreshJournalView();
    }

    var journalAddBtn = document.querySelector("#journal-add");
    if (journalAddBtn) {
      journalAddBtn.addEventListener("click", addJournalCard);
    }
    journalText.addEventListener("keydown", function (event) {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        addJournalCard();
      }
    });
    var journalDiscardBtn = document.querySelector("#journal-discard");
    if (journalDiscardBtn) {
      journalDiscardBtn.addEventListener("click", function () {
        journalText.value = "";
        if (journalCue) journalCue.value = "";
        updateStatusMessage("#journal-feedback", "Draft discarded.");
      });
    }
    var journalCollapse = document.querySelector("#journal-collapse");
    if (journalCollapse) {
      journalCollapse.addEventListener("change", function () {
        var pane = document.querySelector(".journal-pane");
        if (pane) pane.classList.toggle("journal-collapsed", journalCollapse.checked);
      });
    }
    document.querySelectorAll("[data-journal-view]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        currentJournalView = btn.getAttribute("data-journal-view") || "all";
        document.querySelectorAll("[data-journal-view]").forEach(function (other) {
          other.setAttribute("aria-pressed", String(other === btn));
        });
        refreshJournalView();
      });
    });
    function refreshWorkSteps() {
      var steps = document.querySelectorAll(".work-step");
      var checked = document.querySelectorAll(".work-step:checked");
      updateStatusMessage(
        "#work-progress",
        String(checked.length) + " of " + String(steps.length) + " steps complete in this preview"
      );
    }
    document.querySelectorAll(".work-step").forEach(function (checkbox) {
      checkbox.addEventListener("change", refreshWorkSteps);
    });
    refreshJournalView();
    refreshWorkSteps();
  }

  // 8. Work queues preview
  var queueRowsContainer = document.querySelector("#queue-rows");
  if (queueRowsContainer) {
    var activeQueue = "housekeeping";
    var selectedTab = document.querySelector('.queue-tab[aria-pressed="true"]');
    if (selectedTab) activeQueue = selectedTab.getAttribute("data-queue") || "housekeeping";
    var queueSearch = document.querySelector("#queue-search");
    var queueStatus = document.querySelector("#queue-status");
    var ticketDialog = document.querySelector("#ticket-dialog");
    var activeRow = null;
    var arrivalCounter = 100;

    function refreshQueueCounts() {
      var rows = Array.prototype.slice.call(queueRowsContainer.querySelectorAll("tr[data-queue]"));
      document.querySelectorAll(".queue-tab[data-queue]").forEach(function (tab) {
        var key = tab.getAttribute("data-queue");
        var count = rows.filter(function (row) {
          return row.getAttribute("data-queue") === key && row.getAttribute("data-status") !== "Completed";
        }).length;
        var pill = tab.querySelector(".count-pill");
        if (pill) {
          pill.textContent = String(count);
          pill.setAttribute("aria-label", String(count) + " outstanding items");
        }
      });
    }

    function filterQueueRows() {
      var term = queueSearch ? queueSearch.value.trim().toLowerCase() : "";
      var statusFilter = queueStatus ? queueStatus.value : "Outstanding";
      var rows = Array.prototype.slice.call(queueRowsContainer.querySelectorAll("tr[data-queue]"));
      var visible = 0;
      rows.forEach(function (row) {
        var rowQueue = row.getAttribute("data-queue");
        var rowStatus = row.getAttribute("data-status");
        var rowId = (row.getAttribute("data-id") || "").toLowerCase();
        var rowTitle = (row.getAttribute("data-title") || "").toLowerCase();
        var matchesQueue = rowQueue === activeQueue;
        var matchesTerm = !term || rowId.indexOf(term) !== -1 || rowTitle.indexOf(term) !== -1;
        var matchesStatus =
          statusFilter === "All" ||
          (statusFilter === "Outstanding" ? rowStatus !== "Completed" : rowStatus === statusFilter);
        var show = matchesQueue && matchesTerm && matchesStatus;
        row.hidden = !show;
        if (show) visible += 1;
      });
      var emptyRow = document.querySelector("#queue-empty-row");
      if (emptyRow) emptyRow.hidden = visible > 0;
      updateStatusMessage("#queue-count", String(visible) + " items in this view");
    }

    function bindTicketButton(btn) {
      btn.addEventListener("click", function () {
        if (!ticketDialog) return;
        activeRow = btn.closest("tr[data-queue]");
        if (!activeRow) return;
        updateStatusMessage(
          "#ticket-code",
          activeRow.getAttribute("data-id") + " · " + (activeRow.getAttribute("data-queue-name") || activeQueue)
        );
        updateStatusMessage("#ticket-title", activeRow.getAttribute("data-title") || "");
        updateStatusMessage("#ticket-status-badge", activeRow.getAttribute("data-status") || "");
        updateStatusMessage(
          "#ticket-priority-badge",
          (activeRow.getAttribute("data-priority") || "Normal") + " priority"
        );
        updateStatusMessage("#ticket-context", activeRow.getAttribute("data-context") || "");
        updateStatusMessage(
          "#ticket-meta-summary",
          "Owner · " + (activeRow.getAttribute("data-owner") || "Unassigned") + " | Age · " + (activeRow.getAttribute("data-age") || "")
        );
        var noteField = document.querySelector("#ticket-note");
        if (noteField) noteField.value = activeRow.getAttribute("data-note") || "";
        var completeBtn = document.querySelector("#ticket-complete");
        if (completeBtn) {
          completeBtn.disabled = activeRow.getAttribute("data-status") === "Completed";
        }
        ticketDialog.showModal();
      });
    }

    document.querySelectorAll(".queue-tab[data-queue]").forEach(function (tab) {
      tab.addEventListener("click", function () {
        activeQueue = tab.getAttribute("data-queue") || "housekeeping";
        document.querySelectorAll(".queue-tab[data-queue]").forEach(function (other) {
          other.setAttribute("aria-pressed", String(other === tab));
        });
        updateStatusMessage("#queue-title", tab.getAttribute("data-queue-name") || "");
        updateStatusMessage("#queue-description", tab.getAttribute("data-queue-description") || "");
        if (queueSearch) queueSearch.value = "";
        filterQueueRows();
      });
    });

    if (queueSearch) queueSearch.addEventListener("input", filterQueueRows);
    if (queueStatus) queueStatus.addEventListener("change", filterQueueRows);
    document.querySelectorAll("[data-ticket]").forEach(bindTicketButton);

    var arrivalBtn = document.querySelector("#simulate-arrival");
    var rowTpl = document.querySelector("#queue-row-template");
    if (arrivalBtn && rowTpl) {
      arrivalBtn.addEventListener("click", function () {
        arrivalCounter += 1;
        var clone = rowTpl.content.cloneNode(true);
        var tr = clone.querySelector("tr");
        var id = "NEW-" + String(arrivalCounter);
        var activeTab = document.querySelector('.queue-tab[aria-pressed="true"]');
        var qName = activeTab ? activeTab.getAttribute("data-queue-name") : activeQueue;
        tr.setAttribute("data-queue", activeQueue);
        tr.setAttribute("data-queue-name", qName);
        tr.setAttribute("data-id", id);
        tr.setAttribute("data-title", "New item awaiting review");
        tr.setAttribute("data-status", "Ready");
        tr.setAttribute("data-priority", "Normal");
        tr.setAttribute("data-owner", "Unassigned");
        tr.setAttribute("data-age", "Just now");
        tr.setAttribute(
          "data-context",
          "This record was added to the in-memory sample. Queue membership and count update together."
        );
        tr.querySelector(".ticket-reference").textContent = id;
        var linkBtn = tr.querySelector(".ticket-link");
        linkBtn.textContent = "New item awaiting review";
        linkBtn.setAttribute("data-ticket", id);
        bindTicketButton(linkBtn);
        queueRowsContainer.insertBefore(clone, document.querySelector("#queue-empty-row"));
        refreshQueueCounts();
        filterQueueRows();
      });
    }

    var ticketClose = document.querySelector("#ticket-close");
    if (ticketClose && ticketDialog) {
      ticketClose.addEventListener("click", function () {
        ticketDialog.close();
      });
    }
    function applyTicketResolution(newStatus) {
      if (!activeRow || !ticketDialog) return;
      var noteField = document.querySelector("#ticket-note");
      activeRow.setAttribute("data-status", newStatus);
      activeRow.setAttribute("data-note", noteField ? noteField.value : "");
      var badge = activeRow.querySelector(".status");
      if (badge) {
        badge.textContent = newStatus;
        badge.className = "status status-" + newStatus.toLowerCase();
      }
      ticketDialog.close();
      refreshQueueCounts();
      filterQueueRows();
    }
    var completeBtn = document.querySelector("#ticket-complete");
    if (completeBtn) {
      completeBtn.addEventListener("click", function () {
        applyTicketResolution("Completed");
      });
    }
    var deferBtn = document.querySelector("#ticket-defer");
    if (deferBtn) {
      deferBtn.addEventListener("click", function () {
        applyTicketResolution("Waiting");
      });
    }
    refreshQueueCounts();
    filterQueueRows();
  }

  // 9. Catalogue / Elements demos
  document.querySelectorAll("[data-demo]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      updateStatusMessage("#demo-status", btn.getAttribute("data-demo") || "Selected");
    });
  });
  var demoDialogBtn = document.querySelector("#demo-dialog");
  if (demoDialogBtn && window.bootstrap) {
    demoDialogBtn.addEventListener("click", function () {
      var modalEl = document.querySelector("#demo-confirmation");
      if (modalEl) window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
    });
  }
  var showToastBtn = document.querySelector("#show-toast");
  if (showToastBtn && window.bootstrap) {
    showToastBtn.addEventListener("click", function () {
      var toastEl = document.querySelector("#demo-toast");
      if (toastEl) window.bootstrap.Toast.getOrCreateInstance(toastEl).show();
    });
  }
})();

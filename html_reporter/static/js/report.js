// Enhanced virtual table with lazy loading and style matching the provided HTML
class EnhancedVirtualTable {
  constructor(config) {
    this.containerId = config.containerId;
    this.container = document.getElementById(this.containerId);
    this.data = config.data || [];
    this.columns = config.columns || [];
    this.pageSize = 50;  // larger batch size for lazy loading
    this.currentIndex = 0;
    this.sortColumn = config.defaultSortColumn || null;
    this.sortDirection = config.defaultSortDirection || 'desc';
    this.filterFn = null;
    this.searchText = '';
    this.selectedStatuses = new Set(config.defaultSelectedStatuses || []);
    this.visibleData = [];
    this.totalItems = 0;
    this.rowHeight = config.rowHeight || 70; // Taller rows for test info
    this.bufferSize = config.bufferSize || 20; // More buffer rows for smooth scrolling
    this.renderTimeout = null;
    this.customRenderers = config.customRenderers || {};
    this.clickHandlers = config.clickHandlers || {};
    this.onFilterChange = config.onFilterChange;
    this.infiniteScroll = config.infiniteScroll !== false;
    this.isLoading = false;
    this.allDataLoaded = false;

    this.initialize();
  }

  initialize() {
    // Create table structure
    this.container.innerHTML = `
      <div class="card card-table">
        <div class="table-responsive">
          <div class="virtual-table-container">
            <div class="virtual-table-header"></div>
            <div class="virtual-table-body">
              <div class="virtual-table-viewport">
                <div class="virtual-table-content"></div>
              </div>
            </div>
            <div class="virtual-table-footer">
              <div class="virtual-table-info">
                Showing <span class="showing-end">0</span> of <span class="total-entries">0</span> entries
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    // Get references to DOM elements
    this.headerEl = this.container.querySelector('.virtual-table-header');
    this.viewportEl = this.container.querySelector('.virtual-table-viewport');
    this.contentEl = this.container.querySelector('.virtual-table-content');
    this.footerEl = this.container.querySelector('.virtual-table-footer');
    this.infoEl = this.container.querySelector('.virtual-table-info');
    this.searchInputEl = document.querySelector('#searchInput');
    this.showingEnd = this.container.querySelector('.showing-end');
    this.totalEntriesEl = this.container.querySelector('.total-entries');

    // Set viewport height (match the 500px in your example)
    this.viewportEl.style.height = `500px`;
    this.viewportEl.style.overflowY = 'auto';

    // Add event listeners
    this.viewportEl.addEventListener('scroll', this.handleScroll.bind(this));
    this.searchInputEl.addEventListener('input', this.handleSearch.bind(this));

    // Render header
    this.renderHeader();

    // Initial data processing
    this.processData();
  }

  // Replace the renderHeader method with this version
    renderHeader() {
      const headerTable = document.createElement('table');
      headerTable.className = 'table table-striped';
      headerTable.style.tableLayout = 'fixed';
      headerTable.style.width = '100%';

      let headerHTML = `<thead><tr>`;

      this.columns.forEach((column, index) => {
        const sortClass = this.sortColumn === index
          ? (this.sortDirection === 'asc' ? 'sorting_asc' : 'sorting_desc')
          : (column.sortable ? 'sorting' : '');

        headerHTML += `<th class="${sortClass}" ${column.sortable ? 'data-column-index="' + index + '"' : ''}>`;

        if (column.field === 'outcome') {
          // Status column with filter dropdown
          headerHTML += `
            <div class="d-flex align-items-center gap-2">
              <span class="font-weight-bold">${column.label}</span>
              <div class="dropdown status-filter-dropdown" data-bs-auto-close="outside">
                <button class="btn btn-filter dropdown-toggle" type="button" data-bs-toggle="dropdown">
                  <svg fill="currentColor" height="16" viewBox="0 0 16 16" width="16" xmlns="http://www.w3.org/2000/svg">
                    <path d="M1.5 1.5A.5.5 0 0 1 2 1h12a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-.128.334L10 8.692V13.5a.5.5 0 0 1-.342.474l-3 1A.5.5 0 0 1 6 14.5V8.692L1.628 3.834A.5.5 0 0 1 1.5 3.5v-2z"/>
                  </svg>
                </button>
                <div class="dropdown-menu p-2">
                  ${column.filterOptions.map(option => `
                    <div class="form-check">
                      <input checked class="form-check-input" id="status${option.value}" type="checkbox" value="${option.value}">
                      <label class="form-check-label" for="status${option.value}">${option.label}</label>
                    </div>
                  `).join('')}
                  <div class="dropdown-divider"></div>
                  <div class="filter-actions">
                    <button class="btn btn-link" id="selectAll${index}">Select All</button>
                    <button class="btn btn-link" id="clearAll${index}">Clear All</button>
                  </div>
                </div>
              </div>
            </div>
          `;
        } else {
          headerHTML += column.label;
        }

        headerHTML += `</th>`;
      });

      headerHTML += `</tr></thead>`;

      headerTable.innerHTML = headerHTML;
      this.headerEl.appendChild(headerTable);

      // Add sort event listeners
      const sortableHeaders = this.headerEl.querySelectorAll('[data-column-index]');
      sortableHeaders.forEach(header => {
        header.addEventListener('click', () => {
          const columnIndex = parseInt(header.dataset.columnIndex);
          this.handleSort(columnIndex);
        });
      });

      // Add filter event listeners
      this.setupFilterListeners();
    }

  setupFilterListeners() {
    this.columns.forEach((column, index) => {
      if (column.filterable) {
        const selectAllBtn = document.getElementById(`selectAll${index}`);
        const clearAllBtn = document.getElementById(`clearAll${index}`);
        const checkboxes = this.headerEl.querySelectorAll(`.dropdown-menu input[type="checkbox"]`);

        checkboxes.forEach(checkbox => {
          checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
              this.selectedStatuses.add(checkbox.value);
            } else {
              this.selectedStatuses.delete(checkbox.value);
            }
            this.processData();

            if (this.onFilterChange) {
              this.onFilterChange(this.selectedStatuses);
            }
          });
        });

        if (selectAllBtn) {
          selectAllBtn.addEventListener('click', () => {
            checkboxes.forEach(checkbox => {
              checkbox.checked = true;
              this.selectedStatuses.add(checkbox.value);
            });
            this.processData();

            if (this.onFilterChange) {
              this.onFilterChange(this.selectedStatuses);
            }
          });
        }

        if (clearAllBtn) {
          clearAllBtn.addEventListener('click', () => {
            checkboxes.forEach(checkbox => {
              checkbox.checked = false;
              this.selectedStatuses.delete(checkbox.value);
            });
            this.processData();

            if (this.onFilterChange) {
              this.onFilterChange(this.selectedStatuses);
            }
          });
        }
      }
    });
  }

  handleScroll() {
    if (this.renderTimeout) {
      cancelAnimationFrame(this.renderTimeout);
    }

    this.renderTimeout = requestAnimationFrame(() => {
      this.renderVisibleRows();

      // Check if we need to load more data (infinite scroll)
      if (this.infiniteScroll && !this.isLoading && !this.allDataLoaded) {
        const scrollPos = this.viewportEl.scrollTop;
        const scrollHeight = this.viewportEl.scrollHeight;
        const clientHeight = this.viewportEl.clientHeight;

        // Load more when user scrolls to 80% of the current content
        if (scrollPos + clientHeight > scrollHeight * 0.8) {
          this.loadMoreData();
        }
      }
    });
  }

  loadMoreData() {
    if (this.isLoading || this.allDataLoaded) return;

    this.isLoading = true;

    // Calculate next batch of data to display
    const newIndex = this.currentIndex + this.pageSize;
    if (newIndex >= this.visibleData.length) {
      this.allDataLoaded = true;
      this.isLoading = false;
      return;
    }

    this.currentIndex = newIndex;

    // Add loading indicator
    this.showLoadingIndicator();

    // Simulate network delay for smooth UX
    setTimeout(() => {
      this.hideLoadingIndicator();
      this.renderVisibleRows();
      this.updateInfoText();
      this.isLoading = false;
    }, 300);
  }

  showLoadingIndicator() {
    let loadingEl = this.viewportEl.querySelector('.loading-indicator');
    if (!loadingEl) {
      loadingEl = document.createElement('div');
      loadingEl.className = 'loading-indicator';
      loadingEl.innerHTML = `
        <div class="text-center py-3">
          <div class="spinner-border spinner-border-sm text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
          </div>
          <span class="ms-2">Loading more results...</span>
        </div>
      `;
      this.contentEl.appendChild(loadingEl);
    }
  }

  hideLoadingIndicator() {
    const loadingEl = this.viewportEl.querySelector('.loading-indicator');
    if (loadingEl) {
      loadingEl.remove();
    }
  }

  handleSearch(event) {
    this.searchText = event.target.value.toLowerCase();
    this.currentIndex = 0;
    this.allDataLoaded = false;
    this.processData();
  }

  handleSort(columnIndex) {
    if (this.sortColumn === columnIndex) {
      // Toggle sort direction
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortColumn = columnIndex;
      this.sortDirection = 'asc';
    }

    // Update header sort indicators
    const headers = this.headerEl.querySelectorAll('th');
    headers.forEach((header, index) => {
      if (index === columnIndex) {
        header.classList.remove('sorting', 'sorting_asc', 'sorting_desc');
        header.classList.add(this.sortDirection === 'asc' ? 'sorting_asc' : 'sorting_desc');
      } else if (header.classList.contains('sorting_asc') || header.classList.contains('sorting_desc')) {
        header.classList.remove('sorting_asc', 'sorting_desc');
        if (this.columns[index]?.sortable) {
          header.classList.add('sorting');
        }
      }
    });

    this.currentIndex = 0;
    this.allDataLoaded = false;
    this.processData();
  }

  setFilter(filterFn) {
    this.filterFn = filterFn;
    this.currentIndex = 0;
    this.allDataLoaded = false;
    this.processData();
  }

  setSearch(searchText) {
    this.searchText = searchText.toLowerCase();
    this.searchInputEl.value = searchText;
    this.currentIndex = 0;
    this.allDataLoaded = false;
    this.processData();
  }

  processData() {
    // Apply filters
    let filteredData = this.data;

    // Apply status filter
    if (this.selectedStatuses && this.selectedStatuses.size > 0) {
      filteredData = filteredData.filter(item => {
        const status = item.outcome?.toUpperCase() || 'UNKNOWN';
        return this.selectedStatuses.has(status);
      });
    }

    // Apply custom filter
    if (this.filterFn) {
      filteredData = filteredData.filter(this.filterFn);
    }

    // Apply search
    if (this.searchText) {
      filteredData = filteredData.filter(item => {
        // Search in all text fields
        return this.columns.some(column => {
          const value = column.accessor ? column.accessor(item) : item[column.field];
          return value && value.toString().toLowerCase().includes(this.searchText);
        });
      });
    }

    // Sort data
    if (this.sortColumn !== null) {
      const column = this.columns[this.sortColumn];

      filteredData.sort((a, b) => {
        let valueA = column.accessor ? column.accessor(a) : a[column.field];
        let valueB = column.accessor ? column.accessor(b) : b[column.field];

        // Handle custom sorting
        if (column.sortFn) {
          return column.sortFn(valueA, valueB) * (this.sortDirection === 'asc' ? 1 : -1);
        }

        // Default sorting
        if (typeof valueA === 'string') valueA = valueA.toLowerCase();
        if (typeof valueB === 'string') valueB = valueB.toLowerCase();

        if (valueA < valueB) return this.sortDirection === 'asc' ? -1 : 1;
        if (valueA > valueB) return this.sortDirection === 'asc' ? 1 : -1;
        return 0;
      });
    }

    // Store filtered and sorted data
    this.visibleData = filteredData;
    this.totalItems = filteredData.length;
    this.currentIndex = 0;
    this.allDataLoaded = false;

    // Reset scroll position
    this.viewportEl.scrollTop = 0;

    // Update display info
    this.updateInfoText();

    // Render visible rows
    this.renderVisibleRows();
  }

  updateInfoText() {
    const start = this.totalItems > 0 ? 1 : 0;
    const end = Math.min(this.currentIndex + this.pageSize, this.totalItems);

    this.showingEnd.textContent = end;
    this.totalEntriesEl.textContent = this.totalItems;
  }

  renderVisibleRows() {
    // Get the currently visible data batch
    const endIndex = Math.min(this.currentIndex + this.pageSize, this.visibleData.length);
    const visibleData = this.visibleData.slice(0, endIndex);

    if (visibleData.length === 0) {
      this.contentEl.innerHTML = `
        <table class="table table-striped">
          <tbody>
            <tr>
              <td colspan="${this.columns.length}" class="text-center py-4">
                No matching records found
              </td>
            </tr>
          </tbody>
        </table>
      `;
      return;
    }

    // Create table
    let tableHTML = `
      <table class="table table-striped" style="table-layout: fixed; width: 100%;">
        <tbody>
    `;

    // Generate rows
    visibleData.forEach((item, index) => {
      tableHTML += this.renderRow(item, index);
    });

    tableHTML += `
        </tbody>
      </table>
    `;

    // Update DOM
    this.contentEl.innerHTML = tableHTML;

    // Add event listeners to the rendered rows
    this.addRowEventListeners();
  }

  renderRow(item, index) {
    const oddEven = index % 2 === 0 ? 'odd' : 'even';
    let rowHTML = `<tr class="${oddEven}">`;

    this.columns.forEach((column) => {
      const value = column.accessor ? column.accessor(item) : item[column.field];

      // Use custom renderer if provided
      if (column.renderer) {
        rowHTML += `<td>${column.renderer(value, item)}</td>`;
      } else if (this.customRenderers[column.field]) {
        rowHTML += `<td>${this.customRenderers[column.field](value, item)}</td>`;
      } else {
        rowHTML += `<td>${value}</td>`;
      }
    });

    rowHTML += '</tr>';
    return rowHTML;
  }

  addRowEventListeners() {
    // Add click handlers for buttons and other interactive elements
    Object.keys(this.clickHandlers).forEach(selector => {
      const elements = this.contentEl.querySelectorAll(selector);
      elements.forEach((element, index) => {
        // Find the closest row to determine which item this element belongs to
        const row = element.closest('tr');
        if (!row) return;

        // Get the row index
        const rowIndex = Array.from(row.parentElement.children).indexOf(row);
        if (rowIndex === -1) return;

        // Get the data item
        const item = this.visibleData[rowIndex];
        if (!item) return;

        element.addEventListener('click', (event) => {
          this.clickHandlers[selector](event, item, rowIndex);
        });
      });
    });
  }

  refresh() {
    this.processData();
  }

  setData(newData) {
    this.data = newData;
    this.currentIndex = 0;
    this.allDataLoaded = false;
    this.processData();
  }

  getSelectedStatuses() {
    return this.selectedStatuses;
  }
}

// Initialize the enhanced table implementation
document.addEventListener('DOMContentLoaded', function() {
  // Get the test data from the decompressed global variable
  const testData = window.tests || [];

  // Define column configuration
  const columns = [
    {
      field: 'metadata.case_id',
      label: 'Case ID',
      sortable: true,
      accessor: (item) => item.metadata?.case_id || 'N/A',
      sortFn: (a, b) => {
        // Extract numbers from strings like "TEST-123"
        const numA = parseInt(a.match(/\d+/)?.[0] || 0);
        const numB = parseInt(b.match(/\d+/)?.[0] || 0);
        return numA - numB;
      },
      renderer: (value, item) => {
        if (item.metadata?.case_link) {
          return `<a href="${item.metadata.case_link}" target="_blank" title="Open test case info">${value}</a>`;
        }
        return value;
      }
    },
    {
      field: 'test_info',
      label: 'Test',
      sortable: true,
      accessor: (item) => {
        const testTitle = item.metadata?.case_title || '';
        const testName = item.nodeid?.split('::')?.pop() || '';
        return testTitle + ' ' + testName; // For search purposes
      },
      renderer: (value, item) => {
        const testTitle = item.metadata?.case_title || '';
        const testName = item.nodeid?.split('::')?.pop() || '';
        const testPath = item.nodeid || '';

      return `
        <div class="test-title font-weight-semibold">${testTitle}</div>
        <div class="test-name font-weight-regular">${testName}</div>
        <div class="test-path font-weight-light"><a href="${item.github_link}" target="_blank">${testPath}</a></div>
      `;
      }
    },
    {
      field: 'duration',
      label: 'Duration',
      sortable: true,
      sortFn: (a, b) => parseFloat(a) - parseFloat(b),
      accessor: (item) => item.duration || 0,
      renderer: (value, item) => {
        let html = `${value.toFixed(2)}s`;

        // Add warning icon for slow tests
        if (value >= 120) {
          html += `
            <svg class="bi bi-exclamation-triangle-fill" data-bs-placement="right"
                 data-bs-toggle="tooltip" fill="#ff3366" height="16"
                 title="Test is too slow and needs optimization" viewBox="0 0 16 16"
                 width="16" xmlns="http://www.w3.org/2000/svg">
              <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
            </svg>
          `;
        }

        return html;
      }
    },
    {
      field: 'outcome',
      label: 'Status',
      sortable: true,
      filterable: true,
      filterOptions: [
        { value: 'PASSED', label: 'Passed' },
        { value: 'FAILED', label: 'Failed' },
        { value: 'ERROR', label: 'Error' },
        { value: 'RERUN', label: 'Rerun' },
        { value: 'SKIPPED', label: 'Skipped' },
        { value: 'XFAILED', label: 'XFailed' },
        { value: 'XPASSED', label: 'XPassed' }
      ],
      accessor: (item) => item.outcome?.toUpperCase() || 'UNKNOWN',
      renderer: (value, item) => {
        return `<span class="badge badge-${item.outcome}">${value}</span>`;
      }
    },
    {
      field: 'actions',
      label: 'Actions',
      renderer: (value, item) => {
          const modalId = `modal-${item.timestamp.toString().replace(/\./g, '_')}`;
          return `<button class="btn btn-sm btn-primary details-btn font-weight-medium"
                    data-bs-toggle="modal"
                    data-bs-target="#${modalId}"
                    data-test-id="${item.nodeid}"
                    data-timestamp="${item.timestamp}">
                    Details
                  </button>`;
        }
    }
  ];

  // Initialize enhanced virtual table
  const table = new EnhancedVirtualTable({
    containerId: 'resultsTableContainer',
    data: testData,
    columns: columns,
    pageSize: 50,
    defaultSortColumn: 2, // Duration column
    defaultSortDirection: 'desc',
    defaultSelectedStatuses: ['PASSED', 'FAILED', 'ERROR', 'RERUN', 'SKIPPED', 'XFAILED', 'XPASSED'],
    infiniteScroll: true,
    clickHandlers: {
      '.details-btn': (event, item) => {
        // Render test details modal
        renderTestDetailsModal(item);
      }
    },
    onFilterChange: (selectedStatuses) => {
      // Update wave effect based on selected status filters
      updateTestStatusWave(selectedStatuses);
    }
  });

  // Function to update test status wave
  function updateTestStatusWave(outcomes) {
    const wave = document.getElementById('test-status-wave');

    if (!outcomes || outcomes.size === 0) {
      wave.classList.remove('status-failure', 'status-success');
      return;
    }

    // Check if the set contains any failure statuses
    if (outcomes.has('FAILED') || outcomes.has('ERROR')) {
      wave.classList.remove('status-success');
      wave.classList.add('status-failure');
    } else {
      wave.classList.remove('status-failure');
      wave.classList.add('status-success');
    }
  }

  // Add search functionality
    const searchInput = document.querySelector('#searchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        table.setSearch(e.target.value);
      });
    }

  // Summary cards click handlers
  document.querySelectorAll('.summary-card').forEach(card => {
    // Hover effects
    card.addEventListener('mouseenter', function() {
      this.style.transform = 'translateY(-2px)';
      this.style.boxShadow = '0 10px 26px rgba(0, 0, 0, 0.2)';
    });

    card.addEventListener('mouseleave', function() {
      if (!this.classList.contains('active')) {
        this.style.transform = 'none';
        this.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.12)';
      }
    });

    // Click to filter by status
    card.addEventListener('click', function() {
      const clickedStatus = this.dataset.status.toUpperCase();

      // Reset visual state of all cards
      document.querySelectorAll('.summary-card').forEach(c => {
        c.classList.remove('active');
        c.style.transform = 'none';
        c.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.12)';
      });

      // Check if this card is already active
      const isActive = this.classList.contains('active');

      if (isActive) {
        // If active, show all statuses
        table.selectedStatuses = new Set(['PASSED', 'FAILED', 'ERROR', 'RERUN', 'SKIPPED', 'XFAILED', 'XPASSED']);
      } else {
        // If not active, filter to only this status
        table.selectedStatuses = new Set([clickedStatus]);

        // Update visual state
        this.classList.add('active');
        this.style.transform = 'translateY(-3px)';
        this.style.boxShadow = '0 12px 28px rgba(0, 0, 0, 0.25)';
      }

      // Update checkboxes in filter dropdown to match selected statuses
      document.querySelectorAll('.status-filter-dropdown .form-check-input').forEach(checkbox => {
        checkbox.checked = table.selectedStatuses.has(checkbox.value);
      });

      // Refresh table
      table.refresh();
    });
  });

  // Reset all filters button
  const resetAllBtn = document.getElementById('reset-filters');
  if (resetAllBtn) {
    resetAllBtn.addEventListener('click', function() {
      // Reset table filters and sort
      table.selectedStatuses = new Set(['PASSED', 'FAILED', 'ERROR', 'RERUN', 'SKIPPED', 'XFAILED', 'XPASSED']);
      table.sortColumn = 2; // Duration column
      table.sortDirection = 'desc';
      table.currentIndex = 0;
      table.allDataLoaded = false;

      // Reset search
      const searchInput = document.querySelector('#searchInput');
      if (searchInput) {
        searchInput.value = '';
        table.setSearch('');
      }

      // Reset visual state of summary cards
      document.querySelectorAll('.summary-card').forEach(card => {
        card.classList.remove('active');
        card.style.transform = 'none';
        card.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.12)';
      });

      // Update checkboxes in filter dropdown
      document.querySelectorAll('.status-filter-dropdown .form-check-input').forEach(checkbox => {
        checkbox.checked = true;
      });

      // Refresh table
      table.refresh();
    });
  }

  // CSV Export functionality
  document.getElementById('export-csv').addEventListener('click', function() {
    // Use filtered data from the virtual table
    const filteredData = table.visibleData;

    if (filteredData.length === 0) {
      alert('No data to export. Please change filters.');
      return;
    }

    // Create CSV headers with Ukrainian titles
    const headers = ['ID тест сценарію', 'Назва тесту', 'Автотест', 'Тривалість', 'Статус', 'Бізнес процес', 'Посилання на сценарій'];
    let csvContent = headers.join(',') + '\n';

    // Add each filtered row to CSV
    for (let i = 0; i < filteredData.length; i++) {
      const item = filteredData[i];

      const caseId = item.metadata?.case_id || '';
      const testTitle = item.metadata?.case_title || '';
      const testPath = item.nodeid || '';
      const duration = item.duration.toFixed(2);
      const status = item.outcome?.toUpperCase() || '';
      const bpId = item.metadata?.bp_id || '';
      const caseLink = item.metadata?.case_link || '';

      // Escape values for CSV format
      const escapeCSV = (value) => {
        if (value === null || value === undefined) return '';
        return `"${String(value).replace(/"/g, '""')}"`;
      };

      // Create CSV row and add to content
      const csvRow = [
        escapeCSV(caseId),
        escapeCSV(testTitle),
        escapeCSV(testPath),
        escapeCSV(duration),
        escapeCSV(status),
        escapeCSV(bpId),
        escapeCSV(caseLink)
      ].join(',');

      csvContent += csvRow + '\n';
    }

    // Get current date and time for filename
    const now = new Date();
    const dateStr = now.toISOString().replace(/[:.]/g, '_').slice(0, 19);

    // Create download link for the CSV
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    // Set link properties with date in filename
    link.setAttribute('href', url);
    link.setAttribute('download', `test_results_${dateStr}.csv`);
    link.style.visibility = 'hidden';

    // Add to document, click and remove
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });

  // Initialize tooltips for elements in the table
  function initializeTooltips() {
    const tooltipTriggers = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggers.forEach(trigger => {
      if (!bootstrap.Tooltip.getInstance(trigger)) {
        new bootstrap.Tooltip(trigger);
      }
    });
  }

  // Initialize tooltips after table is rendered
  setTimeout(initializeTooltips, 500);
});

function formatDuration(seconds) {
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        const parts = [];
        if (hrs > 0) parts.push(`${hrs.toString().padStart(2, '0')}`);
        parts.push(`${mins.toString().padStart(2, '0')}`);
        parts.push(`${secs.toString().padStart(2, '0')}`);

        return parts.join(':');
    }

function copyToClipboard(text) {
  // Function to show feedback on the button
  function updateButtonTooltip(button, message) {
    if (!button) {
      console.error("Button not found");
      return;
    }

    const tooltip = bootstrap.Tooltip.getInstance(button);
    if (!tooltip) {
      console.warn("Tooltip instance not found, creating new one");
      new bootstrap.Tooltip(button, {
        title: message,
        trigger: 'manual'
      }).show();
    } else {
      button.setAttribute('data-bs-original-title', message);
      tooltip.show();
    }

    setTimeout(function() {
      if (tooltip) {
        tooltip.hide();
        button.setAttribute('data-bs-original-title', 'Copy to clipboard');
      }
    }, 1500);
  }

  // Get the button that triggered this
  const button = document.querySelector(`[onclick="copyToClipboard('${text.replace(/'/g, "\\'")}')"]`);

  // Attempt to write to clipboard using Async Clipboard API
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text)
      .then(function() {
        updateButtonTooltip(button, 'Copied!');
      })
      .catch(function(err) {
        console.error('Async clipboard copy failed:', err);
        fallbackCopyMethod();
      });
  } else {
    // If Async Clipboard API not available, fallback immediately
    fallbackCopyMethod();
  }

  // Fallback copy method
  function fallbackCopyMethod() {
    // Fallback to displaying the text in a prompt for manual copying
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    const copyHotkey = isMac ? '⌘C' : 'CTRL+C';
    window.prompt(`Copy failed. Please manually copy the text below using ${copyHotkey}`, text);

    updateButtonTooltip(button, 'Please copy from prompt');
  }
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    function updateTestStatusWave(outcomes) {
        const wave = document.getElementById('test-status-wave');

        if (!outcomes || outcomes.size === 0) {
            wave.classList.remove('status-failure', 'status-success');
            return;
        }

        // Check if the set contains any failure statuses
        if (outcomes.has('failed') || outcomes.has('error')) {
            wave.classList.remove('status-success');
            wave.classList.add('status-failure');
        } else {
            wave.classList.remove('status-failure');
            wave.classList.add('status-success');
        }
    }

    // Process outcome data once on server-side
    updateTestStatusWave(new Set({{ results|map(attribute='outcome')|unique|list|tojson }}));

    // Initialize the summary
    const summaryContent = document.querySelector('.summary-content');
    if (summaryContent) {
        const stats = {{ stats|tojson }}; // Make sure stats is available in your template
        summaryContent.innerHTML = stats.summary;
    }

    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

    // Configuration settings for test timeline visualization
    const CHART_CONFIG = {
        margin: { top: 15, right: 40, bottom: 10, left: 50 },
        itemHeight: 20,
        itemMargin: 4,
        nodeMargin: 25
    };

    function formatTimestamp(timestamp) {
        const date = new Date(timestamp * 1000);
        return date.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    }

    function sanitizeId(str) {
        return str.replace(/[^\w-]/g, "_");  // Replace invalid characters with "_"
    }
    // Format timestamp to readable format
    function renderTimeline(tests, isBrushUpdate = false) {
    if (!tests || tests.length === 0) {
        return;
    }

    // Get SVG elements
    const chartSvg = d3.select('#timeline-chart');
    const brushSvg = d3.select('#timeline-brush');
    brushSvg.attr('height', 110);

    // Ensure we have the DOM elements
    if (!chartSvg.node() || !brushSvg.node()) {
        console.error('Timeline SVG elements not found!');
        return;
    }

    // Store the global time range - IMPORTANT: Always calculate this
    const globalMinTimestamp = d3.min(tests, d => d.timestamp);
    const globalMaxTimestamp = d3.max(tests, d => d.timestamp + d.duration);

    const svgWidth = chartSvg.node().getBoundingClientRect().width || 800;
    const plotWidth = svgWidth - CHART_CONFIG.margin.left - CHART_CONFIG.margin.right;

    // Filter by minimum duration
    const minDuration = parseFloat(document.getElementById('duration-filter')?.value || '0');

    // Clear ALL previous content
    chartSvg.selectAll('*').remove();
    // Only clear brush if not a brush update
    if (!isBrushUpdate) {
        brushSvg.selectAll('*').remove();
    }

    // Group tests by worker_id
    const testsByWorker = {};
    tests.forEach(test => {
        if (test.duration >= minDuration) {
            if (!testsByWorker[test.worker_id]) {
                testsByWorker[test.worker_id] = [];
            }
            testsByWorker[test.worker_id].push({
                id: test.nodeid.replace(/[:|.]/g, '_'),
                status: test.outcome || 'unknown',
                duration: test.duration,
                timestamp: test.timestamp,
                label: test.metadata.case_title || test.nodeid.split('::').pop() || 'Unknown test'
            });
        }
    });

    // Sort tests within each worker
    Object.values(testsByWorker).forEach(workerTests => {
        workerTests.sort((a, b) => a.timestamp - b.timestamp);
    });

    // Find time range for current view
    const allTests = Object.values(testsByWorker).flat();
    const minTimestamp = d3.min(allTests, d => d.timestamp);
    const maxTimestamp = d3.max(allTests, d => d.timestamp + d.duration);

    // Create time scale using the current view range
    const timeScale = d3.scaleLinear()
        .domain([minTimestamp, maxTimestamp])
        .range([0, plotWidth]);

    // Calculate total height
    const workerCount = Object.keys(testsByWorker).length;
    const totalHeight = (workerCount * (CHART_CONFIG.itemHeight + CHART_CONFIG.nodeMargin + 22))
        + CHART_CONFIG.margin.top + CHART_CONFIG.margin.bottom;

    chartSvg.attr('height', Math.max(totalHeight, 100));

    // Main chart container
    const chart = chartSvg.append('g')
        .attr('transform', `translate(${CHART_CONFIG.margin.left}, ${CHART_CONFIG.margin.top})`);

    // Add header
    const header = chart.append('g')
        .attr('class', 'timeline__slider');

    // Add time axis
    header.append('line')
        .attr('class', 'timeline__slider_track')
        .attr('x1', 0)
        .attr('x2', plotWidth);

    // Add summary text
    header.append('text')
        .attr('transform', `translate(${plotWidth/2}, 20)`)
        .attr('class', 'timeline__slider_text')
        .attr('text-anchor', 'middle')
        .text(`Selected ${allTests.length} tests with duration above ${minDuration.toFixed(1)}s`);

    // Add timestamp range
    const headerText = header.append('g')
        .attr('class', 'timeline__slider_text')
        .attr('transform', 'translate(0, 20)');

    headerText.append('text')
        .attr('x', 0)
        .text(formatTimestamp(minTimestamp));

    headerText.append('text')
        .attr('x', plotWidth)
        .attr('text-anchor', 'end')
        .text(formatTimestamp(maxTimestamp));

    // Create plot area
    const plot = chart.append('g')
        .attr('class', 'timeline__plot')
        .attr('transform', 'translate(0, 40)');

    // Add worker groups
    let yOffset = 0;
    Object.entries(testsByWorker).forEach(([workerId, workerTests]) => {
        const workerGroup = plot.append('g')
            .attr('class', 'timeline__group')
            .attr('transform', `translate(0, ${yOffset})`);

        workerGroup.append('text')
            .attr('class', 'timeline__group_title')
            .attr('x', -40)
            .text(`Worker: ${workerId}`);

        const items = workerGroup.append('g')
            .attr('class', 'timeline__group')
            .attr('transform', 'translate(0, 22)');

        workerTests.forEach((test) => {
            const uniqueId = `${test.id}_${test.timestamp}`;

            const originalTest = tests.find(t =>
                t.nodeid.replace(/[:|.]/g, '_') === test.id &&
                Math.abs(t.timestamp - test.timestamp) < 0.001 &&
                t.duration === test.duration
            );

            let modalId;
            if (originalTest) {
                modalId = `modal-${originalTest.timestamp.toString().replace(/\./g, '_')}`;
            } else {
                console.warn(`Could not find exact match for test: ${test.label}`);
                const fallbackTest = tests.find(t => t.nodeid.replace(/[:|.]/g, '_') === test.id);
                if (fallbackTest) {
                    modalId = `modal-${fallbackTest.timestamp.toString().replace(/\./g, '_')}`;
                } else {
                    modalId = `modal-unknown`;
                }
            }

            const testBar = items.append('rect')
                .attr('class', `timeline__item chart__fill_status_${test.status}`)
                .attr('x', timeScale(test.timestamp))
                .attr('y', 0)
                .attr('width', Math.max(timeScale(test.timestamp + test.duration) - timeScale(test.timestamp), 1))
                .attr('rx', 2)
                .attr('ry', 2)
                .attr('height', CHART_CONFIG.itemHeight)
                .attr('data-bs-toggle', 'modal')
                .attr('data-bs-target', `#${modalId}`)
                .attr('data-testid', uniqueId)
                .style('cursor', 'pointer')
                .attr('tabindex', '0')
                .attr('role', 'button')
                .attr('aria-label', `Test ${test.label}, duration: ${test.duration.toFixed(2)} seconds, status: ${test.status.toUpperCase()}`);

            testBar.append('title')
                .text(`${test.label}\nDuration: ${test.duration.toFixed(2)}s\nStatus: ${test.status.toUpperCase()}`);
        });

        yOffset += CHART_CONFIG.itemHeight + CHART_CONFIG.nodeMargin + 22;
    });

    // Create brush if not updating from brush event
    if (!isBrushUpdate) {
    const brushHeight = 35;

    // Add gradient definition
    const defs = brushSvg.append('defs');
    const gradient = defs.append('linearGradient')
        .attr('id', 'brushGradient')
        .attr('x1', '0%')
        .attr('y1', '0%')
        .attr('x2', '100%')
        .attr('y2', '0%');

    gradient.append('stop')
        .attr('offset', '0%')
        .attr('style', 'stop-color: rgba(255,0,0,0.2)');
    gradient.append('stop')
        .attr('offset', '33%')
        .attr('style', 'stop-color: rgba(0,0,255,0.2)');
    gradient.append('stop')
        .attr('offset', '66%')
        .attr('style', 'stop-color: rgba(0,255,0,0.2)');
    gradient.append('stop')
        .attr('offset', '100%')
        .attr('style', 'stop-color: rgba(255,0,0,0.2)');

    // Create time axis for brush with more detailed ticks
    const timeAxis = d3.axisBottom(timeScale)
        .ticks(10)
        .tickFormat(formatTimestamp);

    const brushContainer = brushSvg.append('g')
        .attr('class', 'timeline__brush')
        .attr('transform', `translate(${CHART_CONFIG.margin.left}, 0)`);

    // Add time axis with proper styling
    brushContainer.append('g')
        .attr('class', 'timeline__brush__axis timeline__brush__axis_x')
        .attr('transform', `translate(0,${brushHeight + 10})`)
        .call(timeAxis);


    const brush = d3.brushX()
        .extent([[0, 0], [plotWidth, brushHeight]])
        .on('brush', brushed)
        .on('end', brushended);

    function brushed(event) {
        if (!event.selection) {
            renderTimeline(tests, true);
            return;
        }

        const [x0, x1] = event.selection.map(timeScale.invert);

        // Update time labels
        updateBrushTimeLabels(event.selection, timeScale);

        const filteredTests = tests.filter(d => {
            const testStart = d.timestamp;
            const testEnd = d.timestamp + d.duration;
            return testStart >= x0 && testEnd <= x1;
        });

        if (filteredTests.length > 0) {
            const scrollPos = window.scrollY;
            renderTimeline(filteredTests, true);
            window.scrollTo(0, scrollPos);
        }
    }

    function brushended(event) {
        if (!event.selection) {
            renderTimeline(tests);
        }
    }

    const brushG = brushContainer.append('g')
        .attr('class', 'brush')
        .call(brush);

    // Set initial brush selection to full width
    brushG.call(brush.move, [0, plotWidth]);

    // Add time labels for brush handles
    brushG.append('g')
        .attr('class', 'brush-time-labels')
        .selectAll('.brush-time-label')
        .data(['start', 'end'])
        .enter()
        .append('text')
        .attr('class', 'brush-time-label')
        .attr('text-anchor', d => d === 'start' ? 'start' : 'end')
        .attr('y', -5);
}


        // Ensure help text for time selection appears only once
        if (!document.querySelector('.timeline__help-text')) {
            brushSvg.append('text')
                .attr('class', 'timeline__help-text')
                .attr('text-anchor', 'middle')
                .attr('x', svgWidth / 2)
                .attr('y', 90) // Changed from 70 to 90 to move it lower
                .text('Click and drag in this area to zoom into specific time range');
        }
    }

function updateBrushTimeLabels(selection, scale) {
    if (!selection) return;

    const [x0, x1] = selection;
    const [t0, t1] = selection.map(scale.invert);

    d3.select('.brush-time-labels')
        .selectAll('.brush-time-label')
        .data([t0, t1])
        .attr('x', (d, i) => i === 0 ? x0 : x1)
        .text(formatTimestamp);
    }

    // Packages collapse functionality
    const packagesHeader = document.querySelector('[aria-controls="packagesCollapse"]');
    const packagesCollapse = document.getElementById('packagesCollapse');

    if (packagesHeader && packagesCollapse) {
        // Initialize Bootstrap collapse
        const bsCollapse = new bootstrap.Collapse(packagesCollapse, {
            toggle: false
        });

        packagesHeader.addEventListener('click', function(e) {
            e.preventDefault();
            const isExpanded = this.getAttribute('aria-expanded') === 'true';
            this.setAttribute('aria-expanded', !isExpanded);
            if (isExpanded) {
                bsCollapse.hide();
            } else {
                bsCollapse.show();
            }
        });

        // Add collapse event listeners
        packagesCollapse.addEventListener('shown.bs.collapse', function() {
            packagesHeader.setAttribute('aria-expanded', 'true');
        });

        packagesCollapse.addEventListener('hidden.bs.collapse', function() {
            packagesHeader.setAttribute('aria-expanded', 'false');
        });
    }

    // Extract screenshots to separate memory space
    const screenshotsData = {};

    // Process screenshots for lazy loading - improved version
    function extractScreenshots(testResults) {
        let count = 0;
        testResults.forEach(test => {
            if (test.screenshot) {
                // Store with both formats of ID to ensure we can find it
                const testId = test.timestamp.toString().replace(/\./g, '_');
                screenshotsData[testId] = test.screenshot;

                // Also store with original timestamp for extra safety
                screenshotsData[test.timestamp.toString()] = test.screenshot;

                count++;

                // Keep the screenshot in the test object as backup
                // We'll delete only after confirming fix works
                // delete test.screenshot;
            }
        });

        console.log(`Extracted ${count} screenshots for lazy loading`);
    }

    // Extract screenshots on page load
    extractScreenshots(window.tests);

    // Reset timeline filter
    const resetFilterBtn = document.getElementById('reset-filter');
    if (resetFilterBtn) {
        resetFilterBtn.addEventListener('click', function() {
            durationSlider.value = 0;
            durationDisplay.textContent = `0s (max: ${maxTestDuration}s)`;

            // Reset brush to full width
            const brushSelection = d3.select('.brush');
            if (!brushSelection.empty()) {
                // Get the current width from the timeline
                const currentWidth = d3.select('#timeline-chart').node().getBoundingClientRect().width
                    - CHART_CONFIG.margin.left - CHART_CONFIG.margin.right;
                const brush = d3.brushX().extent([[0, 0], [currentWidth, 35]]);
                brushSelection.call(brush.move, [0, currentWidth]);
            }

            renderTimeline(tests);
        });
    }

    // Reset all filters
    const resetAllBtn = document.getElementById('reset-filters');
    if (resetAllBtn) {
      resetAllBtn.addEventListener('click', function() {
        // Reset table filters and sort
        table.selectedStatuses = new Set(['PASSED', 'FAILED', 'ERROR', 'RERUN', 'SKIPPED', 'XFAILED', 'XPASSED']);
        table.sortColumn = 2; // Duration column
        table.sortDirection = 'desc';
        table.currentPage = 1;

        // Reset search
        const searchInput = document.querySelector('#searchInput');
        if (searchInput) {
          searchInput.value = '';
          table.setSearch('');
        }

        // Reset visual state of summary cards
        document.querySelectorAll('.summary-card').forEach(card => {
          card.classList.remove('active');
          card.style.transform = 'none';
          card.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.12)';
        });

        // Reset checkboxes in filter dropdown
        document.querySelectorAll('.status-filter-dropdown .form-check-input').forEach(checkbox => {
          checkbox.checked = true;
        });

        // Refresh table
        table.refresh();
      });
    }

    // Modal handlers
    document.querySelectorAll('.modal').forEach(modal => {
        const modalContent = modal.querySelector('.modal-content');
        if (modalContent) {
            modalContent.addEventListener('click', function(e) {
                e.stopPropagation();
            });
        }

        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                const modalInstance = bootstrap.Modal.getInstance(modal);
                if (modalInstance) modalInstance.hide();
            }
        });

        // Simplified focus management
        modal.addEventListener('hide.bs.modal', function() {
            // Remove focus from all focusable elements
            document.activeElement.blur();
        });
    });

    // Loader fade out
    setTimeout(() => {
        const loader = document.getElementById('loader');
        if (loader) {
            loader.classList.add('fade-out');
            setTimeout(() => {
                loader.style.display = 'none';
            }, 300);
        }
    }, 500);

    // Set current year in footer
    document.getElementById('current-year').textContent = new Date().getFullYear();

    // Simplified screenshot loading function
    function loadScreenshot(testId, container) {
      // Clear container first
      container.innerHTML = '';

      if (screenshotsData && screenshotsData[testId]) {
        // Create image element
        const img = document.createElement('img');
        img.className = 'screenshot';
        img.alt = 'Test Screenshot';
        img.src = `data:image/jpeg;base64,${screenshotsData[testId]}`;

        // Add to container
        container.appendChild(img);
      } else {
        console.error(`No screenshot data found for ID: ${testId}`);
        // List available IDs in screenshotsData to help debug
        container.innerHTML = '<div class="alert alert-warning">Screenshot not available</div>';
      }
    }

    // Load screenshot when any modal is shown - improved version
    document.body.addEventListener('shown.bs.modal', function(event) {
        const modal = event.target;
        if (!modal.classList.contains('modal')) return;

        const screenshotContainer = modal.querySelector('.screenshot-container');
        if (screenshotContainer && !screenshotContainer.querySelector('img')) {
            const testId = screenshotContainer.dataset.testId;

            // Try all possible transformations of the ID
            if (testId && screenshotsData[testId]) {
                loadScreenshot(testId, screenshotContainer);
            } else {
                // Try without underscore transformation
                const altTestId = testId.replace(/_/g, '.');
                if (screenshotsData[altTestId]) {
                    loadScreenshot(altTestId, screenshotContainer);
                } else {
                    console.warn('No screenshot data found for test ID:', testId);
                }
            }
        }
    });

    // Initialize tooltips for all modals
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

function renderErrorDetails(error) {
    if (!error) return '';

    const errorLines = error.trim().split('\n');
    const firstLine = errorLines[0] || "";
    const isSoftAssert = firstLine.trim().startsWith("Soft assert failures");

    if (isSoftAssert) {
        // For soft assertions, only show the header line
        return `<h5 class="mb-2">${escapeHtml(firstLine)}</h5>`;
    } else {
        // For regular errors, get the last few lines and identify the header line
        const lastLines = errorLines.length >= 6 ? errorLines.slice(-6) : errorLines;
        const summaryLines = lastLines.slice(0, -1);
        const headerLine = lastLines[lastLines.length - 1];

        return `
          <h5 class="mb-2 font-weight-medium">${escapeHtml(headerLine)}</h5>
          ${summaryLines.map(line => `
            <div class="${line.trim().startsWith('E ') ? 'fw-bold font-weight-bold' : 'font-monospace font-weight-regular'}">
              ${escapeHtml(line)}
            </div>
          `).join('')}
        `;
    }
}

// Helper function for escaping HTML
function escapeHtml(unsafe) {
    if (unsafe == null) return 'N/A';
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function renderTestDetailsModal(test) {
    // Safely replace periods in timestamp
    const safeTimestamp = (test.timestamp || Date.now()).toString().replace(/\./g, '_');
    const modalId = `modal-${safeTimestamp}`;

    // Helper function for safe value extraction
    const safeValue = (value, defaultValue = 'N/A') => {
        return value !== undefined && value !== null ? value : defaultValue;
    };

    // Escape HTML to prevent XSS
    const escapeHtml = (unsafe) => {
        if (unsafe == null) return 'N/A';
        return String(unsafe)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    };

    // Render error section
    const renderErrorSection = () => {
        if (!test.error) return '';

        const errorLines = test.error.trim().split('\n');
        const firstLine = errorLines[0] || "";
        const isSoftAssert = firstLine.trim().startsWith("Soft assert failures");

        let summaryLines, headerLine;
        if (isSoftAssert) {
            summaryLines = [firstLine];
            headerLine = firstLine;
        } else {
            const lastLines = errorLines.length >= 6 ? errorLines.slice(-6) : errorLines;
            summaryLines = lastLines.slice(0, -1);
            headerLine = lastLines[lastLines.length - 1];
        }

        return `
            <div class="row mb-3">
                <div class="col-md-3"><strong>Error:</strong></div>
                <div class="col-md-9">
                    <div class="accordion" id="errorAccordion-${safeTimestamp}">
                        <div class="accordion-item border-0">
                            <div class="error-summary alert alert-danger mb-0 rounded-bottom-0 border-bottom-0">
                                <h5 class="mb-2">${escapeHtml(headerLine)}</h5>
                                ${summaryLines.map(line => `
                                    <div class="${line.trim().startsWith('E ') ? 'fw-bold' : 'font-monospace'}">
                                        ${escapeHtml(line)}
                                    </div>
                                `).join('')}
                            </div>
                            <h2 class="accordion-header m-0">
                                <button class="accordion-button collapsed py-2 bg-light text-dark border border-danger border-top-0 rounded-0 rounded-bottom"
                                        type="button"
                                        data-bs-toggle="collapse"
                                        data-bs-target="#errorDetail-${safeTimestamp}"
                                        aria-expanded="false"
                                        aria-controls="errorDetail-${safeTimestamp}">
                                    Full Error Details
                                </button>
                            </h2>
                            <div id="errorDetail-${safeTimestamp}"
                                 class="accordion-collapse collapse"
                                 data-bs-parent="#errorAccordion-${safeTimestamp}">
                                <div class="accordion-body p-0 border border-danger border-top-0">
                                    <div class="error-message rounded-0">${escapeHtml(test.error)}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    };

    // Render GitHub execution section
    const renderGitHubSection = () => {
        // Only render for failed, error, xfailed, or rerun tests
        const nonPassedStatuses = ['failed', 'error', 'xfailed', 'rerun'];

        // If the test outcome is not in non-passed statuses, return empty string
        if (!nonPassedStatuses.includes(test.outcome.toLowerCase())) {
            return '';
        }

        return `
            <div class="row mb-3">
                <div class="col-md-3"><strong>GitHub execution:</strong></div>
                <div class="col-md-9">
                    <p>This test can be executed by
                        <a href="https://github.com/Goraved/playwright_python_practice/actions"
                            target="_blank"><strong>opening
                            the link</strong></a>, passing the command below into the
                        <strong>TEST_FOLDER</strong>
                        variable, and clicking <strong>New
                            pipeline</strong> button:
                    </p>
                    <div class="code-wrapper position-relative">
                        <pre class="bg-light p-2 rounded"><code
                                class="text-break">${escapeHtml(test.nodeid)}</code></pre>
                        <button class="btn btn-sm btn-primary copy-button position-absolute top-50 end-0 translate-middle-y me-2"
                                data-bs-placement="left"
                                data-bs-toggle="tooltip"
                                onclick="copyToClipboard('${test.nodeid.replace(/'/g, "\\'")}')"
                                title="Copy to clipboard">
                            <svg fill="currentColor" height="16" viewBox="0 0 16 16" width="16"
                                    xmlns="http://www.w3.org/2000/svg">
                                <path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"/>
                                <path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        `;
    };

    // Render phase durations
    const renderPhaseDurations = () => {
        if (!test.phase_durations) return '';

        return `
            <div class="row mb-3">
                <div class="col-md-3"><strong>Phases:</strong></div>
                <div class="col-md-9">
                    <div class="d-flex flex-column gap-1">
                        ${test.phase_durations.setup ? `
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge bg-info" data-bs-toggle="tooltip" data-bs-placement="top"
                                  title="Preparation time before the test case execution (fixture setup)">
                                Setup
                            </span>
                            <span class="${test.phase_durations.setup < 15 ? 'duration-normal' : 'duration-slow'}">
                                ${test.phase_durations.setup.toFixed(2)}s
                            </span>
                            ${test.phase_durations.setup >= 15 ? `
                            <svg class="bi bi-clock-fill" data-bs-placement="right"
                                 data-bs-toggle="tooltip"
                                 fill="#ff9900"
                                 height="14" title="Setup phase is slow, consider optimizing your fixtures"
                                 viewBox="0 0 16 16"
                                 width="14" xmlns="http://www.w3.org/2000/svg">
                                <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zM8 3.5a.5.5 0 0 0-1 0V9a.5.5 0 0 0 .252.434l3.5 2a.5.5 0 0 0 .496-.868L8 8.71V3.5z"/>
                            </svg>
                            ` : ''}
                        </div>
                        ` : ''}

                        ${test.phase_durations.call ? `
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge bg-primary" data-bs-toggle="tooltip" data-bs-placement="top"
                                  title="Actual test execution time (the test function itself)">
                                Call
                            </span>
                            <span class="${test.phase_durations.call < 120 ? 'duration-normal' : 'duration-slow'}">
                                ${test.phase_durations.call.toFixed(2)}s
                            </span>
                            ${test.phase_durations.call >= 120 ? `
                            <svg class="bi bi-clock-fill" data-bs-placement="right"
                                 data-bs-toggle="tooltip"
                                 fill="#ff3366"
                                 height="14" title="Test execution is slow, optimize your test logic"
                                 viewBox="0 0 16 16"
                                 width="14" xmlns="http://www.w3.org/2000/svg">
                                <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zM8 3.5a.5.5 0 0 0-1 0V9a.5.5 0 0 0 .252.434l3.5 2a.5.5 0 0 0 .496-.868L8 8.71V3.5z"/>
                            </svg>
                            ` : ''}
                        </div>
                        ` : ''}

                        ${test.phase_durations.teardown ? `
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge bg-secondary" data-bs-toggle="tooltip" data-bs-placement="top"
                                  title="Cleanup time after test execution (fixture teardown)">
                                Teardown
                            </span>
                            <span class="${test.phase_durations.teardown < 10 ? 'duration-normal' : 'duration-slow'}">
                                ${test.phase_durations.teardown.toFixed(2)}s
                            </span>
                            ${test.phase_durations.teardown >= 10 ? `
                            <svg class="bi bi-clock-fill" data-bs-placement="right"
                                 data-bs-toggle="tooltip"
                                 fill="#ff9900"
                                 height="14" title="Teardown phase is slow, check your cleanup operations"
                                 viewBox="0 0 16 16"
                                 width="14" xmlns="http://www.w3.org/2000/svg">
                                <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zM8 3.5a.5.5 0 0 0-1 0V9a.5.5 0 0 0 .252.434l3.5 2a.5.5 0 0 0 .496-.868L8 8.71V3.5z"/>
                            </svg>
                            ` : ''}
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    };

    // Render metadata section
    const renderMetadataSection = () => {
        if (!test.metadata || Object.keys(test.metadata).length === 0) return '';

        return `
            <div class="row mb-3">
                <div class="col-md-3"><strong>Metadata:</strong></div>
                <div class="col-md-9">
                    <table class="table table-sm">
                        <tbody>
                        ${Object.entries(test.metadata).map(([key, value]) => `
                            <tr>
                                <td>${key === 'xfail_reason' ? 'bug' : escapeHtml(key)}</td>
                                <td>
                                    ${key === 'xfail_reason' && value ? `
                                    <div class="d-flex align-items-center gap-2">
                                        <a class="text-decoration-none d-flex align-items-center gap-1"
                                           href="${escapeHtml(value)}"
                                           target="_blank"
                                           title="Open bug in new tab">
                                            <span>𓆣</span>
                                            <span class="text-primary">${escapeHtml(value)}</span>
                                            <svg class="ms-1" fill="currentColor" height="10"
                                                 viewBox="0 0 16 16" width="10" xmlns="http://www.w3.org/2000/svg">
                                                <path d="M8.636 3.5a.5.5 0 0 0-.5-.5H1.5A1.5 1.5 0 0 0 0 4.5v10A1.5 1.5 0 0 0 1.5 16h10a1.5 1.5 0 0 0 1.5-1.5V7.864a.5.5 0 1 0-1 0V14.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-10a.5.5 0 0 1 .5-.5h6.636a.5.5 0 0 0 .5-.5z"
                                                      fill-rule="evenodd"/>
                                                <path d="M16 .5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0 0 1h3.793L6.146 9.146a.5.5 0 1 0 .708.708L15 1.707V5.5a.5.5 0 0 0 1 0v-5z"
                                                      fill-rule="evenodd"/>
                                            </svg>
                                        </a>
                                    </div>
                                    ` : key === 'case_link' ? `
                                    <a class="d-flex align-items-center gap-1" href="${escapeHtml(value)}" target="_blank">
                                        ${escapeHtml(value)}
                                        <svg fill="currentColor" height="10" viewBox="0 0 16 16"
                                             width="10" xmlns="http://www.w3.org/2000/svg">
                                            <path d="M8.636 3.5a.5.5 0 0 0-.5-.5H1.5A1.5 1.5 0 0 0 0 4.5v10A1.5 1.5 0 0 0 1.5 16h10a1.5 1.5 0 0 0 1.5-1.5V7.864a.5.5 0 1 0-1 0V14.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-10a.5.5 0 0 1 .5-.5h6.636a.5.5 0 0 0 .5-.5z"
                                                  fill-rule="evenodd"/>
                                            <path d="M16 .5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0 0 1h3.793L6.146 9.146a.5.5 0 1 0 .708.708L15 1.707V5.5a.5.5 0 0 0 1 0v-5z"
                                                  fill-rule="evenodd"/>
                                        </svg>
                                    </a>
                                    ` : escapeHtml(value)}
                                </td>
                            </tr>
                        `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    };

    // Render test steps and logs
    const renderTestStepsAndLogs = () => {
        return `
            <div class="row">
                ${test.description ? `
                <div class="col-md-6">
                    <h6 class="mb-2 mt-3"><strong>Test Steps:</strong></h6>
                    <ol>
                        ${test.description.split('\n').map((step) => {
                            const trimmedStep = step.trim();
                            if (!trimmedStep) return '';

                            // Handle bullet points
                            if (trimmedStep[0] === '-') {
                                return `<li class="list-unstyled">${escapeHtml(trimmedStep)}</li>`;
                            }

                            // Handle numbered steps (preserve original numbering)
                            const numMatch = trimmedStep.match(/^(\d+)\.(.+)/);
                            if (numMatch) {
                                return `<li value="${numMatch[1]}">${escapeHtml(numMatch[2].trim())}</li>`;
                            }

                            return `<li>${escapeHtml(trimmedStep)}</li>`;
                        }).filter(Boolean).join('')}
                    </ol>
                </div>
                ` : ''}
                ${test.logs ? `
                <div class="col-md-6">
                    <h6 class="mb-2 mt-3"><strong>Test Timeline:</strong></h6>
                    <div class="log-container">
                        <div class="timeline-tree">
                            ${test.logs.map((log, index) => {
                                // Calculate indentation based on leading spaces
                                const indent = (log.match(/^\s*/)[0].length / 2) || 0;

                                // Split into name and duration
                                const parts = log.trim().split(': ');
                                if (parts.length !== 2) return '';

                                const [name, duration] = parts;
                                const durationValue = parseFloat(duration.split(' ')[0]);
                                const isSlow = durationValue > 5;

                                return `
                                    <div class="timeline-item" style="--indent: ${indent}">
                                        <div class="d-flex align-items-center gap-2">
                                            <div class="timeline-dot" ${isSlow ? 'style="background: #E83A5F;"' : ''}></div>
                                            <div class="timeline-content">
                                                <div class="timeline-title font-weight-medium">${escapeHtml(name)}</div>
                                                 <div class="timeline-duration font-weight-light ${isSlow ? 'text-danger' : 'text-muted'}">
                                                   ${escapeHtml(duration)}
                                                 </div>
                                            </div>
                                        </div>
                                        ${index < test.logs.length - 1 ? '<div class="timeline-line"></div>' : ''}
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                </div>
                ` : ''}
            </div>
        `;
    };

    // Render captured logs
    const renderCapturedLogsSection = () => {
        if (!test.caplog && !test.capstderr && !test.capstdout) return '';

        return `
            <div class="row mt-4">
                <div class="col-12">
                    <ul class="nav nav-tabs" id="logTabs-${safeTimestamp}" role="tablist">
                        ${test.caplog ? `
                        <li class="nav-item" role="presentation">
                            <button aria-controls="caplog"
                                    aria-selected="true" class="nav-link active"
                                    data-bs-target="#caplog-${safeTimestamp}"
                                    data-bs-toggle="tab"
                                    id="caplog-tab-${safeTimestamp}"
                                    role="tab" type="button">Captured Log
                            </button>
                        </li>
                        ` : ''}
                        ${test.capstderr ? `
                        <li class="nav-item" role="presentation">
                            <button aria-controls="stderr"
                                    aria-selected="false"
                                    class="nav-link ${!test.caplog ? 'active' : ''}"
                                    data-bs-target="#stderr-${safeTimestamp}"
                                    data-bs-toggle="tab"
                                    id="stderr-tab-${safeTimestamp}"
                                    role="tab" type="button">Stderr
                            </button>
                        </li>
                        ` : ''}
                        ${test.capstdout ? `
                        <li class="nav-item" role="presentation">
                            <button aria-controls="stdout"
                                    aria-selected="false"
                                    class="nav-link ${!test.caplog && !test.capstderr ? 'active' : ''}"
                                    data-bs-target="#stdout-${safeTimestamp}"
                                    data-bs-toggle="tab"
                                    id="stdout-tab-${safeTimestamp}"
                                    role="tab" type="button">Stdout
                            </button>
                        </li>
                        ` : ''}
                    </ul>
                    <div class="tab-content mt-2" id="logTabsContent-${safeTimestamp}">
                        ${test.caplog ? `
                        <div aria-labelledby="caplog-tab"
                             class="tab-pane fade show active"
                             id="caplog-${safeTimestamp}"
                             role="tabpanel">
                            <div class="log-container">
                                <pre>${escapeHtml(test.caplog)}</pre>
                            </div>
                        </div>
                        ` : ''}
                        ${test.capstderr ? `
                        <div aria-labelledby="stderr-tab"
                             class="tab-pane fade ${!test.caplog ? 'show active' : ''}"
                             id="stderr-${safeTimestamp}"
                             role="tabpanel">
                            <div class="log-container">
                                <pre>${escapeHtml(test.capstderr)}</pre>
                            </div>
                        </div>
                        ` : ''}
                        ${test.capstdout ? `
                        <div aria-labelledby="stdout-tab"
                             class="tab-pane fade ${!test.caplog && !test.capstderr ? 'show active' : ''}"
                             id="stdout-${safeTimestamp}"
                             role="tabpanel">
                            <div class="log-container">
                                <pre>${escapeHtml(test.capstdout)}</pre>
                            </div>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    };

    // Render screenshot section
    const renderScreenshotSection = () => {
        if (!test.screenshot) return '';
        return `
            <div class="row">
                <div class="col screenshot-container" data-test-id="${safeTimestamp}">
                    <!-- Screenshot will be loaded on demand -->
                    <div class="d-flex justify-content-center align-items-center p-4 text-muted">
                        <div class="spinner-border spinner-border-sm me-2" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <span>Loading screenshot...</span>
                    </div>
                </div>
            </div>
        `;
    };

    // Create modal element
    const modalElement = document.createElement('div');
    modalElement.id = modalId;
    modalElement.className = 'modal fade';
    modalElement.setAttribute('tabindex', '-1');

    // Full modal content
    modalElement.innerHTML = `
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                ${test.rerun ? `
                <div class="row mb-3">
                    <div class="col-md-3"><strong>Rerun Status:</strong></div>
                    <div class="col-md-9">
                         <span class="badge badge-${safeValue(test.rerun.outcome, 'unknown')}">
                         ${escapeHtml(safeValue(test.rerun.outcome, 'UNKNOWN').toUpperCase())}
                         </span>
                    </div>
                </div>
                <div class="row mb-3">
                    <div class="col-md-3"><strong>Rerun Duration:</strong></div>
                    <div class="col-md-9">
                        ${test.rerun.duration.toFixed(2)}s
                    </div>
                </div>
                ` : ''}
                <div class="modal-header">
                      <h5 class="modal-title gradient-text font-weight-semibold">
                        ${escapeHtml(safeValue(
                            test.metadata?.case_title ||
                            test.nodeid?.split('::').pop(),
                            'Unnamed Test'
                        ))}
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <!-- Basic Test Info -->
                    <div class="row mb-3">
                        <div class="col-md-3"><strong>Test Info:</strong></div>
                        <div class="col-md-9">
                            <a href="${safeValue(test.github_link, '#')}" target="_blank" title="Open automation test in GitHub">
                                ${escapeHtml(test.nodeid?.split('::').pop() || 'N/A')}
                            </a>
                        </div>
                    </div>

                    <div class="row mb-3">
                        <div class="col-md-3"><strong>Case ID:</strong></div>
                        <div class="col-md-9">
                            <a href="${safeValue(test.metadata?.case_link, '#')}" target="_blank" title="Open test case info">
                                ${escapeHtml(test.metadata?.case_id || 'N/A')}
                            </a>
                        </div>
                    </div>

                    <div class="row mb-3">
                        <div class="col-md-3"><strong>Status:</strong></div>
                        <div class="col-md-9">
                            <span class="badge badge-${safeValue(test.outcome, 'unknown')}">
                            ${escapeHtml(safeValue(test.outcome, 'UNKNOWN').toUpperCase())}
                            </span>
                        </div>
                    </div>

                    ${test.error_phase ? `
                    <div class="row mb-3">
                        <div class="col-md-3"><strong>Error Phase:</strong></div>
                        <div class="col-md-9">
                            <span class="badge bg-danger">
                                ${escapeHtml(test.error_phase.toUpperCase())}
                            </span>
                            <small class="text-muted ms-2">Test failed during ${escapeHtml(test.error_phase)} phase</small>
                        </div>
                    </div>
                    ` : ''}

                    <div class="row mb-3">
                        <div class="col-md-3"><strong>Duration:</strong></div>
                        <div class="col-md-9 d-flex align-items-center gap-2">
                            <span class="${test.duration < 120 ? 'duration-normal' : 'duration-slow'}">
                            ${safeValue(test.duration ? test.duration.toFixed(2) + 's' : null, 'N/A')}
                            </span>
                            ${test.duration >= 120 ? `
                            <svg class="bi bi-exclamation-triangle-fill" data-bs-placement="right"
                                 data-bs-toggle="tooltip"
                                 fill="#ff3366"
                                 height="16" title="Test is too slow and needs optimization" viewBox="0 0 16 16"
                                 width="16" xmlns="http://www.w3.org/2000/svg">
                                <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
                            </svg>
                            ` : ''}
                        </div>
                    </div>

                    ${renderErrorSection()}
                    ${renderPhaseDurations()}

                    <div class="row mb-3">
                        <div class="col-md-3"><strong>Timestamp:</strong></div>
                        <div class="col-md-9">
                            ${escapeHtml(safeValue(test.formatted_timestamp || test.timestamp, 'N/A'))}
                        </div>
                    </div>

                    ${test.skip_reason ? `
                    <div class="row mb-3">
                        <div class="col-md-3"><strong>Skip Reason:</strong></div>
                        <div class="col-md-9">
                            <div class="d-flex align-items-center gap-2">
                                <span>${escapeHtml(test.skip_reason)}</span>
                            </div>
                        </div>
                    </div>
                    ` : ''}

                    ${test.worker_id && test.worker_id !== "master" ? `
                    <div class="row mb-3">
                        <div class="col-md-3"><strong>Worker:</strong></div>
                        <div class="col-md-9">
                            <span class="badge bg-secondary">${escapeHtml(test.worker_id)}</span>
                        </div>
                    </div>
                    ` : ''}

                    ${renderGitHubSection()}
                    ${renderMetadataSection()}
                    ${renderTestStepsAndLogs()}
                    ${renderCapturedLogsSection()}
                    ${renderScreenshotSection()}
                </div>
            </div>
        </div>
    `;

    // Append to body
    document.body.appendChild(modalElement);

    // Initialize modal and show it
    try {
        // Ensure Bootstrap and its Modal are available
        if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {
            console.error('Bootstrap Modal not available');
            throw new Error('Bootstrap Modal not available');
        }

        // Small timeout to ensure DOM is updated
        setTimeout(() => {
            // Create and show modal
            const modalInstance = new bootstrap.Modal(modalElement);
            modalInstance.show();

            // Initialize tooltips
            const tooltips = modalElement.querySelectorAll('[data-bs-toggle="tooltip"]');
            tooltips.forEach(tooltip => {
                new bootstrap.Tooltip(tooltip);
            });

            // Cleanup on close
            modalElement.addEventListener('hidden.bs.modal', () => {
                modalInstance.dispose();
                modalElement.remove();
            });
        }, 10);
    } catch (error) {
        console.error('Modal initialization error:', error);

        // Fallback display method
        modalElement.classList.add('show');
        modalElement.style.display = 'block';

        // Manual close handling
        const closeButton = modalElement.querySelector('.btn-close');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                modalElement.style.display = 'none';
                modalElement.remove();
            });
        }
    }
}

// Event listener for details button clicks
document.addEventListener('DOMContentLoaded', function() {
    const table = document.getElementById('resultsTable');
    if (!table) return;

    table.addEventListener('click', function(event) {
        const detailsButton = event.target.closest('[data-bs-toggle="modal"]');
        if (!detailsButton) return;

        const modalId = detailsButton.getAttribute('data-bs-target').replace('#', '');
        const test = window.tests.find(t => {
            const safeTimestamp = t.timestamp.toString().replace(/\./g, '_');
            return `modal-${safeTimestamp}` === modalId;
        });

        if (test) {
            renderTestDetailsModal(test);
        } else {
            console.error('No matching test found for modal ID:', modalId);
        }
    });
});

// Lazy loading for timeline data
document.addEventListener('DOMContentLoaded', function() {
    // Timeline lazy loading
    let timelineLoaded = false;
    const timelineContainer = document.getElementById('timelineContainer');

    // Add event listener for bootstrap collapse event
    if (timelineContainer) {
        timelineContainer.addEventListener('shown.bs.collapse', function() {
            if (!timelineLoaded) {
                // Use setTimeout to allow the UI to update before processing data
                setTimeout(loadTimelineData, 50);
            }
        });
    }

    function loadTimelineData() {
        const timelineLoader = document.getElementById('timeline-loader');
        const timelineContent = document.getElementById('timeline-container');
        const timelineFilter = document.getElementById('timeline-filter');
        const timelineHelpText = document.getElementById('timeline-help-text');

        if (!timelineLoader || !timelineContent || !timelineFilter) {
            console.error('Timeline elements not found');
            return;
        }

        // Use the embedded timeline_data variable
        const data = window.timeline_data || [];

        try {
            // Initialize timeline with the data
            const minTestDuration = Math.floor(d3.min(data, d => d.duration) || 0);
            const maxTestDuration = Math.ceil(d3.max(data, d => d.duration) || 10);

            // Duration filter setup
            const durationSlider = document.getElementById('duration-filter');
            const durationDisplay = document.getElementById('min-duration-display');

            if (durationSlider && durationDisplay) {
                durationSlider.min = 0;
                durationSlider.max = maxTestDuration;
                durationSlider.step = 1;
                durationSlider.value = 0;
                durationDisplay.textContent = `0s (max: ${maxTestDuration}s)`;

                durationSlider.addEventListener('input', function() {
                    const value = parseFloat(this.value);
                    durationDisplay.textContent = `${Math.round(value)}s (max: ${maxTestDuration}s)`;
                    renderTimeline(data);
                });
            }

            // Initialize timeline
            renderTimeline(data);

            // Force resize to ensure proper width
            setTimeout(function() {
                window.dispatchEvent(new Event('resize'));

                // Fix the click handlers for timeline items after rendering
                setupTimelineItemClickHandlers();
            }, 100);

            // Reset timeline filter button
            const resetFilterBtn = document.getElementById('reset-filter');
            if (resetFilterBtn) {
                resetFilterBtn.addEventListener('click', function() {
                    durationSlider.value = 0;
                    durationDisplay.textContent = `0s (max: ${maxTestDuration}s)`;

                    // Reset brush to full width
                    const brushSelection = d3.select('.brush');
                    if (!brushSelection.empty()) {
                        // Get the current width from the timeline
                        const currentWidth = d3.select('#timeline-chart').node().getBoundingClientRect().width * 0.95
                            - CHART_CONFIG.margin.left - CHART_CONFIG.margin.right;
                        const brush = d3.brushX().extent([[0, 0], [currentWidth, 35]]);
                        brushSelection.call(brush.move, [0, currentWidth]);
                    }

                    renderTimeline(data);

                    // Re-apply click handlers after reset
                    setTimeout(setupTimelineItemClickHandlers, 50);
                });
            }

            // Hide loader and show timeline components
            timelineLoader.classList.add('d-none');
            timelineContent.classList.remove('d-none');
            timelineFilter.classList.remove('d-none');

            // Show the help text
            if (timelineHelpText) {
                timelineHelpText.classList.remove('d-none');
            }

            // Add window resize handler
            window.addEventListener('resize', function() {
                renderTimeline(data);
                // Re-apply click handlers after resize
                setTimeout(setupTimelineItemClickHandlers, 50);
            });

            // Store the original function
            if (typeof window.renderTimeline === 'function') {
                const originalRenderTimeline = window.renderTimeline;

                // Replace with a wrapped version that adds click handlers
                window.renderTimeline = function() {
                    // Call the original function with all arguments
                    originalRenderTimeline.apply(this, arguments);

                    // Set up click handlers after rendering
                    setTimeout(setupTimelineItemClickHandlers, 50);
                };
            }

            // Mark as loaded
            timelineLoaded = true;
        }
        catch (error) {
            console.error('Error rendering timeline:', error);
            if (timelineLoader) {
                timelineLoader.innerHTML = `
                    <div class="alert alert-danger">
                        Failed to load timeline data. Error: ${error.message}
                    </div>
                `;
            }
        }
    }

    // Function to set up click handlers for timeline items
    function setupTimelineItemClickHandlers() {
        // Select all timeline items with the timeline__item class
        const timelineItems = document.querySelectorAll('.timeline__item');

        timelineItems.forEach(item => {
            // Remove existing click handlers to prevent duplicates
            item.removeEventListener('click', timelineItemClickHandler);

            // Add our click event listener directly
            item.addEventListener('click', timelineItemClickHandler);

            // Make sure the cursor shows it's clickable
            item.style.cursor = 'pointer';

            // Ensure proper accessibility
            if (!item.hasAttribute('role')) {
                item.setAttribute('role', 'button');
            }
            if (!item.hasAttribute('tabindex')) {
                item.setAttribute('tabindex', '0');
            }

            // Add keyboard support for accessibility
            item.removeEventListener('keydown', timelineItemKeyHandler);
            item.addEventListener('keydown', timelineItemKeyHandler);
        });
    }

    // Separate handler for keyboard events
    function timelineItemKeyHandler(e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            timelineItemClickHandler.call(this, e);
        }
    }

    // Improved click handler for timeline items
    function timelineItemClickHandler(e) {
        e.preventDefault();
        e.stopPropagation();

        // Get the test ID and modal target
        const testBar = this;
        const modalTarget = testBar.getAttribute('data-bs-target');
        const testId = testBar.getAttribute('data-testid');

        if (!window.tests || !window.tests.length) {
            console.error('No tests data available in window.tests');
            return;
        }

        try {
            let test = null;

            // First attempt: Try to find test by direct modal ID match
            if (modalTarget) {
                const modalId = modalTarget.replace('#', '');
                const timestampStr = modalId.replace('modal-', '');
                const timestamp = parseFloat(timestampStr.replace(/_/g, '.'));

                test = window.tests.find(t => Math.abs(t.timestamp - timestamp) < 0.001);
            }

            // Second attempt: Try to find test by testId attribute
            if (!test && testId) {
                const parts = testId.split('_');
                if (parts.length >= 2) {
                    const nodeId = parts[0];
                    const timestamp = parseFloat(parts.slice(1).join('_').replace(/_/g, '.'));

                    test = window.tests.find(t => {
                        return t.nodeid.replace(/[:|.]/g, '_') === nodeId &&
                               Math.abs(t.timestamp - timestamp) < 0.001;
                    });
                }
            }

            // Third attempt: Try by status and position
            if (!test) {
                // Get the status class
                const statusClass = Array.from(testBar.classList).find(cls =>
                    cls.startsWith('chart__fill_status_'));

                if (statusClass) {
                    const status = statusClass.replace('chart__fill_status_', '');

                    // Try to find a test with matching status that hasn't been displayed yet
                    test = window.tests.find(t => t.outcome === status);
                }
            }

            // If we found a test, render its modal
            if (test) {
                if (typeof window.renderTestDetailsModal === 'function') {
                    window.renderTestDetailsModal(test);
                } else {
                    console.error('renderTestDetailsModal function not available');
                    alert('Cannot display test details: rendering function is missing');
                }
            } else {
                console.error('No matching test found for clicked timeline item');
                // Give the user some feedback
                alert('Could not find test details for this timeline item');
            }

        } catch (error) {
            console.error('Error handling timeline item click:', error);
        }
    }

    // Add an additional direct event listener to the timeline chart for better event capture
    const timelineChart = document.getElementById('timeline-chart');
    if (timelineChart) {
        timelineChart.addEventListener('click', function(event) {
            const testBar = event.target.closest('.timeline__item');
            if (testBar) {
                // Call our handler directly with the correct this binding
                timelineItemClickHandler.call(testBar, event);
            }
        });
    }

    // Fix for extra white space when timeline is collapsed
    const timelineToggle = document.querySelector('.timeline-toggle-button');

    if (timelineContainer && timelineToggle) {
        // Initial adjustment on page load
        adjustFooterPosition();

        // Adjust when timeline collapse state changes
        timelineContainer.addEventListener('hidden.bs.collapse', adjustFooterPosition);
        timelineContainer.addEventListener('shown.bs.collapse', adjustFooterPosition);

        // Also adjust on window resize
        window.addEventListener('resize', adjustFooterPosition);

        function adjustFooterPosition() {
            // Force browser reflow/repaint to eliminate whitespace
            document.body.style.minHeight = '100vh';
            setTimeout(() => {
                document.body.style.minHeight = '';
            }, 50);
        }
    }
});

// Replace this existing table initialization code in report.js
document.addEventListener('DOMContentLoaded', function() {
  // Get the test data from the decompressed global variable
  const testData = window.tests || [];

  // Define column configuration
  const columns = [
    {
      field: 'metadata.case_id',
      label: 'Case ID',
      sortable: true,
      accessor: (item) => item.metadata?.case_id || 'N/A',
      renderer: (value, item) => {
        if (item.metadata?.case_link) {
          return `<a href="${item.metadata.case_link}" target="_blank" title="Open test case info">${value}</a>`;
        }
        return value;
      }
    },
    {
      field: 'test_info',
      label: 'Test',
      sortable: true,
      accessor: (item) => {
        const testTitle = item.metadata?.case_title || '';
        const testName = item.nodeid?.split('::')?.pop() || '';
        return testTitle + ' ' + testName; // For search purposes
      },
      renderer: (value, item) => {
        const testTitle = item.metadata?.case_title || '';
        const testName = item.nodeid?.split('::')?.pop() || '';
        const testPath = item.nodeid || '';

        return `
          <div class="test-title">${testTitle}</div>
          <div class="test-name">${testName}</div>
          <div class="test-path"><a href="${item.github_link}" target="_blank">${testPath}</a></div>
        `;
      }
    },
    {
      field: 'duration',
      label: 'Duration',
      sortable: true,
      sortFn: (a, b) => parseFloat(a) - parseFloat(b),
      accessor: (item) => item.duration || 0,
      renderer: (value, item) => {
        let html = `${value.toFixed(2)}s`;

        // Add warning icon for slow tests
        if (value >= 120) {
          html += `
            <svg class="bi bi-exclamation-triangle-fill" data-bs-placement="right"
                 data-bs-toggle="tooltip" fill="#ff3366" height="16"
                 title="Test is too slow and needs optimization" viewBox="0 0 16 16"
                 width="16" xmlns="http://www.w3.org/2000/svg">
              <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
            </svg>
          `;
        }

        return html;
      }
    },
    {
      field: 'outcome',
      label: 'Status',
      sortable: true,
      filterable: true,
      filterOptions: [
        { value: 'PASSED', label: 'Passed' },
        { value: 'FAILED', label: 'Failed' },
        { value: 'ERROR', label: 'Error' },
        { value: 'RERUN', label: 'Rerun' },
        { value: 'SKIPPED', label: 'Skipped' },
        { value: 'XFAILED', label: 'XFailed' },
        { value: 'XPASSED', label: 'XPassed' }
      ],
      accessor: (item) => item.outcome?.toUpperCase() || 'UNKNOWN',
      renderer: (value, item) => {
        return `<span class="badge badge-${item.outcome}">${value}</span>`;
      }
    },
    {
      field: 'actions',
      label: 'Actions',
      renderer: (value, item) => {
        const modalId = `modal-${item.timestamp.toString().replace(/\./g, '_')}`;
        return `<button class="btn btn-sm btn-primary details-btn"
                  data-bs-toggle="modal"
                  data-bs-target="#${modalId}"
                  data-test-id="${item.nodeid}"
                  data-timestamp="${item.timestamp}">
                  Details
                </button>`;
      }
    }
  ];

  // Initialize virtual table
  const table = new VirtualTable({
    containerId: 'resultsTableContainer',
    data: testData,
    columns: columns,
    pageSize: 20,
    height: 600,
    defaultSortColumn: 2, // Duration column
    defaultSortDirection: 'desc',
    defaultSelectedStatuses: ['PASSED', 'FAILED', 'ERROR', 'RERUN', 'SKIPPED', 'XFAILED', 'XPASSED'],
    clickHandlers: {
      '.details-btn': (event, item) => {
        // Render test details modal
        renderTestDetailsModal(item);
      }
    },
    onFilterChange: (selectedStatuses) => {
      // Update wave effect based on selected status filters
      updateTestStatusWave(selectedStatuses);
    }
  });

  // Function to update test status wave
  function updateTestStatusWave(outcomes) {
    const wave = document.getElementById('test-status-wave');

    if (!outcomes || outcomes.size === 0) {
      wave.classList.remove('status-failure', 'status-success');
      return;
    }

    // Check if the set contains any failure statuses
    if (outcomes.has('FAILED') || outcomes.has('ERROR')) {
      wave.classList.remove('status-success');
      wave.classList.add('status-failure');
    } else {
      wave.classList.remove('status-failure');
      wave.classList.add('status-success');
    }
  }

  // Add search functionality
  const searchInput = document.querySelector('#searchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      table.setSearch(e.target.value);
    });
  }

  // Summary cards click handlers
  document.querySelectorAll('.summary-card').forEach(card => {
    // Hover effects
    card.addEventListener('mouseenter', function() {
      this.style.transform = 'translateY(-2px)';
      this.style.boxShadow = '0 10px 26px rgba(0, 0, 0, 0.2)';
    });

    card.addEventListener('mouseleave', function() {
      if (!this.classList.contains('active')) {
        this.style.transform = 'none';
        this.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.12)';
      }
    });

    // Click to filter by status
    card.addEventListener('click', function() {
      const clickedStatus = this.dataset.status.toUpperCase();

      // Reset visual state of all cards
      document.querySelectorAll('.summary-card').forEach(c => {
        c.classList.remove('active');
        c.style.transform = 'none';
        c.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.12)';
      });

      // Check if this card is already active
      const isActive = this.classList.contains('active');

      if (isActive) {
        // If active, show all statuses
        table.selectedStatuses = new Set(['PASSED', 'FAILED', 'ERROR', 'RERUN', 'SKIPPED', 'XFAILED', 'XPASSED']);
      } else {
        // If not active, filter to only this status
        table.selectedStatuses = new Set([clickedStatus]);

        // Update visual state
        this.classList.add('active');
        this.style.transform = 'translateY(-3px)';
        this.style.boxShadow = '0 12px 28px rgba(0, 0, 0, 0.25)';
      }

      // Update checkboxes in filter dropdown to match selected statuses
      document.querySelectorAll('.status-filter-dropdown .form-check-input').forEach(checkbox => {
        checkbox.checked = table.selectedStatuses.has(checkbox.value);
      });

      // Refresh table
      table.refresh();
    });
  });

  // Reset all filters button
  const resetAllBtn = document.getElementById('reset-filters');
  if (resetAllBtn) {
    resetAllBtn.addEventListener('click', function() {
      // Reset table filters and sort
      table.selectedStatuses = new Set(['PASSED', 'FAILED', 'ERROR', 'RERUN', 'SKIPPED', 'XFAILED', 'XPASSED']);
      table.sortColumn = 2; // Duration column
      table.sortDirection = 'desc';
      table.currentPage = 1;

      // Reset search
      const searchInput = document.querySelector('#searchInput');
      if (searchInput) {
        searchInput.value = '';
        table.setSearch('');
      }

      // Reset visual state of summary cards
      document.querySelectorAll('.summary-card').forEach(card => {
        card.classList.remove('active');
        card.style.transform = 'none';
        card.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.12)';
      });

      // Update checkboxes in filter dropdown
      document.querySelectorAll('.status-filter-dropdown .form-check-input').forEach(checkbox => {
        checkbox.checked = true;
      });

      // Refresh table
      table.refresh();
    });
  }

  // CSV Export functionality
  document.getElementById('export-csv').addEventListener('click', function() {
    // Use filtered data from the virtual table
    const filteredData = table.visibleData;

    if (filteredData.length === 0) {
      alert('No data to export. Please change filters.');
      return;
    }

    // Create CSV headers with Ukrainian titles
    const headers = ['ID тест сценарію', 'Назва тесту', 'Автотест', 'Тривалість', 'Статус', 'Бізнес процес', 'Посилання на сценарій'];
    let csvContent = headers.join(',') + '\n';

    // Add each filtered row to CSV
    for (let i = 0; i < filteredData.length; i++) {
      const item = filteredData[i];

      const caseId = item.metadata?.case_id || '';
      const testTitle = item.metadata?.case_title || '';
      const testPath = item.nodeid || '';
      const duration = item.duration.toFixed(2);
      const status = item.outcome?.toUpperCase() || '';
      const bpId = item.metadata?.bp_id || '';
      const caseLink = item.metadata?.case_link || '';

      // Escape values for CSV format
      const escapeCSV = (value) => {
        if (value === null || value === undefined) return '';
        return `"${String(value).replace(/"/g, '""')}"`;
      };

      // Create CSV row and add to content
      const csvRow = [
        escapeCSV(caseId),
        escapeCSV(testTitle),
        escapeCSV(testPath),
        escapeCSV(duration),
        escapeCSV(status),
        escapeCSV(bpId),
        escapeCSV(caseLink)
      ].join(',');

      csvContent += csvRow + '\n';
    }

    // Get current date and time for filename
    const now = new Date();
    const dateStr = now.toISOString().replace(/[:.]/g, '_').slice(0, 19);

    // Create download link for the CSV
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    // Set link properties with date in filename
    link.setAttribute('href', url);
    link.setAttribute('download', `test_results_${dateStr}.csv`);
    link.style.visibility = 'hidden';

    // Add to document, click and remove
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });

  // Initialize tooltips for elements in the table
  function initializeTooltips() {
    const tooltipTriggers = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggers.forEach(trigger => {
      if (!bootstrap.Tooltip.getInstance(trigger)) {
        new bootstrap.Tooltip(trigger);
      }
    });
  }

  // Initialize tooltips after table is rendered
  setTimeout(initializeTooltips, 500);

  // Re-initialize tooltips after page change
  table.prevBtn.addEventListener('click', () => setTimeout(initializeTooltips, 100));
  table.nextBtn.addEventListener('click', () => setTimeout(initializeTooltips, 100));
});
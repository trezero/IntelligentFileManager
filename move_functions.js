// Move-related functions for Downloads Manager

// Current recommendation being mapped to a destination
let currentRecommendation = '';

// Show the move files modal
function showMoveModal() {
    if (selectedFiles.size === 0) return;
    
    // Group selected files by recommendation
    const recommendationGroups = {};
    
    // Process each selected file
    selectedFiles.forEach(filePath => {
        // Find the file object
        const fileObj = filteredFiles.find(f => f.path === filePath);
        if (!fileObj) return;
        
        // Extract the recommendation (without the "Move to" prefix)
        let recommendation = fileObj.recommendation;
        if (recommendation.toLowerCase().startsWith('move to ')) {
            recommendation = recommendation.substring(8).trim();
        }
        
        // Group by recommendation
        if (!recommendationGroups[recommendation]) {
            recommendationGroups[recommendation] = [];
        }
        recommendationGroups[recommendation].push(filePath);
    });
    
    // Build the UI for recommendations
    const container = document.getElementById('recommendations-container');
    container.innerHTML = '';
    
    for (const recommendation in recommendationGroups) {
        const files = recommendationGroups[recommendation];
        
        // Create a recommendation group UI
        const groupDiv = document.createElement('div');
        groupDiv.className = 'recommendation-group';
        groupDiv.style.marginBottom = '15px';
        groupDiv.style.padding = '10px';
        groupDiv.style.backgroundColor = '#f8f9fa';
        groupDiv.style.borderRadius = '4px';
        
        // Get destination from mapping if it exists
        const destination = folderMappings[recommendation] || '';
        
        // Create the group content
        groupDiv.innerHTML = `
            <div class="recommendation-header" style="margin-bottom: 8px;">
                <strong>${recommendation}</strong> (${files.length} files)
            </div>
            <div class="destination-row" style="display: flex; align-items: center; gap: 10px;">
                <input type="text" class="destination-input" 
                       data-recommendation="${recommendation}" 
                       value="${destination}" 
                       placeholder="Select destination folder..."
                       style="flex-grow: 1; padding: 6px;">
                <button class="select-folder-btn" 
                        data-recommendation="${recommendation}"
                        style="white-space: nowrap;">
                    Browse...
                </button>
            </div>
            <div class="file-list" style="margin-top: 8px; font-size: 12px; color: #777;">
                ${files.length > 3 
                    ? `${files.slice(0, 3).map(f => f.split('/').pop().split('\\').pop()).join(', ')} and ${files.length - 3} more...`
                    : files.map(f => f.split('/').pop().split('\\').pop()).join(', ')}
            </div>
        `;
        
        container.appendChild(groupDiv);
    }
    
    // Set up browse button event listeners
    document.querySelectorAll('.select-folder-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const recommendation = e.target.dataset.recommendation;
            showFolderSelectModalForRecommendation(recommendation);
        });
    });
    
    // Update move count
    document.getElementById('move-count').textContent = selectedFiles.size;
    
    // Show the modal
    document.getElementById('move-modal').style.display = 'flex';
}

// Hide the move files modal
function hideMoveModal() {
    document.getElementById('move-modal').style.display = 'none';
}

// Show folder selection modal for a specific recommendation
function showFolderSelectModalForRecommendation(recommendation) {
    currentRecommendation = recommendation;
    document.getElementById('recommendation-name').textContent = recommendation;
    
    // Pre-fill with any existing mapping
    document.getElementById('folder-path').value = folderMappings[recommendation] || '';
    
    // Show the modal
    document.getElementById('folder-select-modal').style.display = 'flex';
}

// Show folder selection modal for a manual destination
function showFolderSelectModal() {
    currentRecommendation = 'manual';
    document.getElementById('recommendation-name').textContent = 'Custom Destination';
    document.getElementById('folder-path').value = '';
    document.getElementById('folder-select-modal').style.display = 'flex';
}

// Hide folder selection modal
function hideFolderSelectModal() {
    document.getElementById('folder-select-modal').style.display = 'none';
}

// Confirm folder selection
function confirmFolderSelection() {
    const path = document.getElementById('folder-path').value.trim();
    
    if (!path) {
        showToast('Please enter a valid folder path', 'error');
        return;
    }
    
    if (currentRecommendation === 'manual') {
        // Create a new row in the recommendations container
        const container = document.getElementById('recommendations-container');
        const groupDiv = document.createElement('div');
        groupDiv.className = 'recommendation-group manual-destination';
        groupDiv.style.marginBottom = '15px';
        groupDiv.style.padding = '10px';
        groupDiv.style.backgroundColor = '#f8f9fa';
        groupDiv.style.borderRadius = '4px';
        
        groupDiv.innerHTML = `
            <div class="recommendation-header" style="margin-bottom: 8px;">
                <strong>Custom Destination</strong>
            </div>
            <div class="destination-row" style="display: flex; align-items: center; gap: 10px;">
                <input type="text" class="destination-input" 
                       data-recommendation="manual" 
                       value="${path}" 
                       style="flex-grow: 1; padding: 6px;">
                <button class="select-folder-btn" 
                        data-recommendation="manual"
                        style="white-space: nowrap;">
                    Browse...
                </button>
            </div>
        `;
        
        container.appendChild(groupDiv);
        
        // Add event listener to the new browse button
        const browseBtn = groupDiv.querySelector('.select-folder-btn');
        browseBtn.addEventListener('click', () => {
            showFolderSelectModalForRecommendation('manual');
        });
    } else {
        // Update existing input field
        const input = document.querySelector(`.destination-input[data-recommendation="${currentRecommendation}"]`);
        if (input) {
            input.value = path;
        }
        
        // Save to folder mappings
        folderMappings[currentRecommendation] = path;
        localStorage.setItem('folderMappings', JSON.stringify(folderMappings));
    }
    
    // Hide the folder selection modal
    hideFolderSelectModal();
}

// Move selected files to destinations
async function moveSelectedFiles() {
    if (selectedFiles.size === 0) {
        hideMoveModal();
        return;
    }
    
    // Get all destination inputs
    const destinationInputs = document.querySelectorAll('.destination-input');
    
    // Group files by destination
    const filesByDestination = {};
    
    // Check that all destinations are specified
    let allDestinationsSpecified = true;
    
    destinationInputs.forEach(input => {
        const destination = input.value.trim();
        const recommendation = input.dataset.recommendation;
        
        if (!destination) {
            allDestinationsSpecified = false;
            input.style.borderColor = '#e74c3c';
            return;
        }
        
        // Reset border if previously highlighted
        input.style.borderColor = '';
        
        // Find files with this recommendation
        selectedFiles.forEach(filePath => {
            const fileObj = filteredFiles.find(f => f.path === filePath);
            if (!fileObj) return;
            
            let fileRecommendation = fileObj.recommendation;
            if (fileRecommendation.toLowerCase().startsWith('move to ')) {
                fileRecommendation = fileRecommendation.substring(8).trim();
            }
            
            // If this file matches the recommendation or we're using a manual destination
            if (fileRecommendation === recommendation || recommendation === 'manual') {
                if (!filesByDestination[destination]) {
                    filesByDestination[destination] = [];
                }
                filesByDestination[destination].push(filePath);
            }
        });
    });
    
    // If any destinations are missing, show error and return
    if (!allDestinationsSpecified) {
        showToast('Please specify all destination folders', 'error');
        return;
    }
    
    // Disable the move button while moving
    const moveBtn = document.getElementById('confirm-move-btn');
    moveBtn.disabled = true;
    moveBtn.textContent = 'Moving...';
    
    // Save folder mappings for future use
    destinationInputs.forEach(input => {
        const recommendation = input.dataset.recommendation;
        if (recommendation !== 'manual') {
            folderMappings[recommendation] = input.value.trim();
        }
    });
    localStorage.setItem('folderMappings', JSON.stringify(folderMappings));
    
    // Perform the move operations
    let successCount = 0;
    let failureCount = 0;
    
    // Process each destination
    for (const destination in filesByDestination) {
        const files = filesByDestination[destination];
        
        try {
            const response = await fetch('/api/move', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    files: files,
                    destination: destination
                })
            });
            
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // Update counts
            const moveSuccesses = result.results.filter(r => r.success).length;
            const moveFailures = result.results.filter(r => !r.success).length;
            
            successCount += moveSuccesses;
            failureCount += moveFailures;
            
            // Log any errors
            if (moveFailures > 0) {
                console.warn('Failed to move some files:', 
                    result.results.filter(r => !r.success).map(r => `${r.path}: ${r.error}`));
            }
            
        } catch (error) {
            console.error(`Error moving files to ${destination}:`, error);
            failureCount += files.length;
        }
    }
    
    // Update UI after move operations
    // Apply optimistic updates - remove successfully moved files from the UI
    let filesToRemove = [];
    for (const destination in filesByDestination) {
        filesToRemove = [...filesToRemove, ...filesByDestination[destination]];
    }
    
    // Remove from our data model
    for (const category in downloadsData.categories) {
        downloadsData.categories[category].files = downloadsData.categories[category].files.filter(
            file => !filesToRemove.includes(file.path)
        );
    }
    
    // Remove from filtered files
    filteredFiles = filteredFiles.filter(file => !filesToRemove.includes(file.path));
    
    // Update UI
    renderCategories();
    filterFiles();
    initializeChart();
    updateStats();
    
    // Show result toast
    if (failureCount > 0) {
        showToast(`Moved ${successCount} files, ${failureCount} files could not be moved`, 'warning');
    } else {
        showToast(`Successfully moved ${successCount} files`, 'success');
    }
    
    // Clear selection and hide modal
    selectedFiles.clear();
    updateActionButtons();
    hideMoveModal();
    
    // Reload data to ensure UI is in sync
    setTimeout(() => {
        fetch('claudeDownloadIndex.json')
            .then(response => response.json())
            .then(data => {
                downloadsData = data;
                processData();
                console.log('Data refreshed in background after move operation');
            })
            .catch(e => console.log('Background refresh failed, will update on next action'));
    }, 500);
}
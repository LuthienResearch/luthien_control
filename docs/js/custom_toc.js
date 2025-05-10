document.addEventListener('DOMContentLoaded', function () {
    debug = false;
    function debugLog(message) {
        if (debug) {
            console.log(message);
        }
    }

    function escapeHtml(unsafe) {
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }

    // New recursive function to highlight text within a node while preserving HTML structure
    function highlightTextInNode(node, searchTerm) {
        let matchFound = false;
        const lowerSearchTerm = searchTerm.toLowerCase();

        if (node.nodeType === Node.TEXT_NODE) {
            const nodeText = node.textContent;
            const lowerNodeText = nodeText.toLowerCase();
            const matchIndex = lowerNodeText.indexOf(lowerSearchTerm);

            if (matchIndex !== -1) {
                matchFound = true;
                const beforeText = nodeText.substring(0, matchIndex);
                const matchedText = nodeText.substring(matchIndex, matchIndex + searchTerm.length);
                const afterText = nodeText.substring(matchIndex + searchTerm.length);

                const strongNode = document.createElement('strong');
                strongNode.textContent = matchedText;

                const fragment = document.createDocumentFragment();
                if (beforeText) fragment.appendChild(document.createTextNode(beforeText));
                fragment.appendChild(strongNode);
                if (afterText) fragment.appendChild(document.createTextNode(afterText));
                
                node.parentNode.replaceChild(fragment, node);
            }
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            // Do not recurse into script or style tags, or our own highlight tags
            if (node.nodeName === 'SCRIPT' || node.nodeName === 'STYLE' || node.nodeName === 'STRONG') {
                return false;
            }
            // Iterate backwards through child nodes because replacing a node can affect the NodeList
            for (let i = node.childNodes.length - 1; i >= 0; i--) {
                if (highlightTextInNode(node.childNodes[i], searchTerm)) {
                    matchFound = true;
                }
            }
        }
        return matchFound;
    }

    function filterToc(tocList, searchTerm) {
        const allNavItems = tocList.querySelectorAll('li.md-nav__item');
        const lowerSearchTerm = searchTerm.toLowerCase();

        allNavItems.forEach(item => {
            const link = item.querySelector(':scope > a.md-nav__link');
            if (!link || !link.dataset.originalHtml) { // Ensure originalHtml was stored
                // If it wasn't (e.g. an item not processed by toggle setup), try to store it now
                // This is a fallback, ideally all filterable links should have it stored during init.
                if (link && !link.dataset.originalHtml) link.dataset.originalHtml = link.innerHTML;
                if (!link || !link.dataset.originalHtml) return; // Still no luck, skip.
            }

            // Get text for matching from originalHTML (stripping HTML tags and icon)
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = link.dataset.originalHtml;
            const iconInOriginal = tempDiv.querySelector('span.toc-toggle-icon');
            if (iconInOriginal) iconInOriginal.remove(); // Remove icon for text extraction
            const originalLinkText = tempDiv.textContent.trim();
            const itemText = originalLinkText.toLowerCase();

            item.style.display = ''; // Default to visible
            link.innerHTML = link.dataset.originalHtml; // Restore original HTML first

            if (lowerSearchTerm === "") {
                // All visible, original HTML restored. Expansions persist.
            } else {
                const overallMatchIndex = itemText.indexOf(lowerSearchTerm); // Check if there's a match anywhere
                if (overallMatchIndex !== -1) {
                    // Matched. Item is already visible. Now, highlight the match carefully.
                    const tempHighlightContainer = document.createElement('div');
                    tempHighlightContainer.innerHTML = link.dataset.originalHtml; // Use original HTML as base
                    
                    highlightTextInNode(tempHighlightContainer, searchTerm);
                    
                    link.innerHTML = tempHighlightContainer.innerHTML; // Set link to newly highlighted HTML

                    // Expand all collapsible parents
                    let parentLi = item.parentElement?.closest('li.md-nav__item');
                    while (parentLi && tocList.contains(parentLi)) {
                        parentLi.style.display = '';
                        const togglerLink = parentLi.querySelector(':scope > a.md-nav__link.toc-toggle');
                        const nestedNav = parentLi.querySelector(':scope > nav.md-nav');
                        if (togglerLink && nestedNav && togglerLink.getAttribute('aria-expanded') === 'false') {
                            nestedNav.style.display = 'block';
                            togglerLink.setAttribute('aria-expanded', 'true');
                        }
                        parentLi = parentLi.parentElement?.closest('li.md-nav__item');
                    }
                } else {
                    // No match, hide the item. Original HTML is already restored.
                    item.style.display = 'none';
                }
            }
        });
    }

    function createTocSearchBox(containerElement, tocListElement) {
        const searchInput = document.createElement('input');
        searchInput.setAttribute('type', 'text');
        searchInput.setAttribute('placeholder', 'Filter API items...');
        searchInput.setAttribute('id', 'toc-filter-input');
        searchInput.style.width = 'calc(100% - 10px)'; // Adjust width to fit padding
        searchInput.style.padding = '6px';
        searchInput.style.marginBottom = '0px';
        searchInput.style.border = '1px solid #ccc';
        searchInput.style.borderRadius = '4px';
        searchInput.style.boxSizing = 'border-box';

        containerElement.insertBefore(searchInput, tocListElement);

        searchInput.addEventListener('input', function() {
            filterToc(tocListElement, this.value);
        });
        return searchInput;
    }

    // Find the active primary navigation item, which should contain the integrated TOC
    const activePrimaryNavItem = document.querySelector('nav.md-nav--primary li.md-nav__item--active');
    debugLog('Active Primary Nav Item:', activePrimaryNavItem);

    // Find the primary sidebar itself, which contains the nav.md-nav--primary
    const primarySidebar = document.querySelector('div.md-sidebar.md-sidebar--primary');
    debugLog('Primary Sidebar Element:', primarySidebar);

    if (!primarySidebar) {
        console.error('Could not find the primary sidebar (div.md-sidebar.md-sidebar--primary). Resizing cannot be enabled.');
        // We might still want the rest of the TOC functionality to work, so don't return yet
        // unless the TOC logic absolutely depends on primarySidebar for other things besides resizing.
    }

    if (!activePrimaryNavItem) {
        console.error('Could not find the active primary navigation item. TOC cannot be located.');
        return;
    }

    // Within the active primary nav item, find the TOC's ul element
    // This is the nav.md-nav--secondary that holds the page-specific TOC
    const tocNavElement = activePrimaryNavItem.querySelector(':scope > nav.md-nav--secondary');
    debugLog('TOC Nav Element (within active primary nav item):', tocNavElement);

    if (!tocNavElement) {
        console.error('Could not find nav.md-nav--secondary within the active primary nav item.');
        return;
    }
    
    const tocList = tocNavElement.querySelector(':scope > ul.md-nav__list[data-md-component="toc"]');
    debugLog('TOC List Element (ul[data-md-component="toc"]):', tocList);

    if (tocList) {
        // Create and insert search box BEFORE processing items for collapsibility
        createTocSearchBox(tocNavElement, tocList);

        // Create and add the resizer handle if the primary sidebar exists
        if (primarySidebar) {
            const resizer = document.createElement('div');
            resizer.setAttribute('id', 'toc-resizer');
            // Style will be applied via CSS, but basic ID is good.
            primarySidebar.appendChild(resizer); // Append to the sidebar itself
            debugLog('TOC Resizer handle added to primary sidebar.');
        }

        // Select ALL li.md-nav__item elements within the TOC structure at any depth
        const allNavItems = tocList.querySelectorAll('li.md-nav__item');
        debugLog('Found', allNavItems.length, 'potential nav items in the integrated TOC.');

        allNavItems.forEach((item, index) => {
            if (index < 5) {
                debugLog(`Processing Nav Item ${index}:`, item);
            }
        
            const itemLink = item.querySelector(':scope > a.md-nav__link');
            const nestedNav = item.querySelector(':scope > nav.md-nav');
        
            if (index < 5) {
                debugLog(`  Item ${index} Link:`, itemLink);
                debugLog(`  Item ${index} Nested Nav:`, nestedNav);
            }
        
            if (itemLink) {
                // --- START MODULE LINK MODIFICATION ---
                const originalLinkTextContent = itemLink.textContent.trim();
                const moduleRegex = /^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)+$/;
                if (moduleRegex.test(originalLinkTextContent)) {
                    const newHref = `#${originalLinkTextContent}`;
                    debugLog(`  Item ${index} (${originalLinkTextContent}) identified as a module. Setting href to "${newHref}".`);
                    itemLink.setAttribute('href', newHref);
                }
                // --- END MODULE LINK MODIFICATION ---
        
                // --- ORIGINAL COLLAPSIBILITY AND originalHtml LOGIC (RESTORED AND INTEGRATED) ---
                if (nestedNav) { // Item has a nested navigation structure
                    const subList = nestedNav.querySelector(':scope > ul.md-nav__list');
                    if (subList && subList.children.length > 0) { // And it has children to toggle
                        debugLog(`  Item ${index} (${itemLink.textContent.trim()}) is being made collapsible.`);
                        itemLink.style.cursor = 'pointer';
                        itemLink.classList.add('toc-toggle');
        
                        const toggleIcon = document.createElement('span');
                        toggleIcon.classList.add('toc-toggle-icon');
                        toggleIcon.innerHTML = '&#9658;'; 
        
                        itemLink.prepend(toggleIcon);
                        
                        if (toggleIcon.nextSibling) { 
                            toggleIcon.style.marginRight = '0.3em';
                        }
                        // Store original HTML AFTER icon is prepended
                        itemLink.dataset.originalHtml = itemLink.innerHTML;
        
                        nestedNav.style.display = 'none';
                        itemLink.setAttribute('aria-expanded', 'false');
        
                        itemLink.addEventListener('click', function (event) {
                            if (event.target.closest('.toc-toggle-icon')) {
                                event.preventDefault(); 
                                event.stopPropagation();
                                const isExpanded = nestedNav.style.display === 'block';
                                nestedNav.style.display = isExpanded ? 'none' : 'block';
                                itemLink.setAttribute('aria-expanded', String(!isExpanded));
                            }
                        });
                    } else { // Has a nestedNav, but it's empty or has no list. Treat as non-collapsible for icon/event purposes.
                        if (index < 10) { 
                            debugLog(`  Item ${index} (${itemLink.textContent.trim()}) has an empty/no-sublist nestedNav, not making collapsible.`);
                        }
                        // Store original HTML if not already set. This captures link state after module href change.
                        if (!itemLink.dataset.originalHtml) {
                            itemLink.dataset.originalHtml = itemLink.innerHTML;
                        }
                    }
                } else { // No nestedNav, definitely a leaf node or non-collapsible.
                    // Store original HTML for them as well so filter can restore them
                    // This captures link state after module href change.
                    if (!itemLink.dataset.originalHtml) {
                         itemLink.dataset.originalHtml = itemLink.innerHTML;
                    }
                }
            } else { // No itemLink found for this md-nav__item
                if (index < 10) {
                    debugLog(`  Item ${index} does not have a direct link (a.md-nav__link).`);
                }
            }
        });
    } else {
        console.error('TOC list (ul.md-nav__list[data-md-component="toc"]) not found within the identified TOC nav element.');
    }

    function expandActiveTocItem() {
        const activePrimaryNavItemForExpansion = document.querySelector('nav.md-nav--primary li.md-nav__item--active');
        if (!activePrimaryNavItemForExpansion) {
            debugLog('expandActiveTocItem: Active primary nav item not found.');
            return;
        }
        const tocNavElementForExpansion = activePrimaryNavItemForExpansion.querySelector(':scope > nav.md-nav--secondary');
        if (!tocNavElementForExpansion) {
            debugLog('expandActiveTocItem: TOC nav element (md-nav--secondary) not found.');
            return;
        }
        const currentTocList = tocNavElementForExpansion.querySelector(':scope > ul.md-nav__list[data-md-component="toc"]');
        if (!currentTocList) {
            debugLog('expandActiveTocItem: Main TOC list (ul[data-md-component="toc"]) not found.');
            return;
        }

        const hash = window.location.hash;
        debugLog('expandActiveTocItem: Hash is', hash);
        if (!hash || hash === '#') return;

        const targetId = decodeURIComponent(hash.substring(1));
        // Construct selector for the link in TOC. Attribute value needs to be quoted.
        const targetTocLinkSelector = `a.md-nav__link[href="#${targetId.replace(/"/g, '\"')}"]`;
        
        const targetTocLink = currentTocList.querySelector(targetTocLinkSelector);
        debugLog('expandActiveTocItem: Target ID:', targetId, 'Selector:', targetTocLinkSelector, 'Found Link:', targetTocLink);

        if (targetTocLink) {
            let currentElementForExpansion = targetTocLink; 
            while (currentElementForExpansion && currentElementForExpansion !== currentTocList && currentTocList.contains(currentElementForExpansion)) {
                const containingListItem = currentElementForExpansion.closest('li.md-nav__item');
                if (!containingListItem) break;

                const parentUl = containingListItem.parentElement; 
                if (parentUl && parentUl.matches('ul.md-nav__list')) {
                    const parentNav = parentUl.parentElement; 
                    if (parentNav && parentNav.matches('nav.md-nav')) {
                        const controllerLi = parentNav.parentElement; 
                        if (controllerLi && controllerLi.matches('li.md-nav__item') && currentTocList.contains(controllerLi)) {
                            const togglerLink = controllerLi.querySelector(':scope > a.md-nav__link.toc-toggle');
                            const submenuToExpand = controllerLi.querySelector(':scope > nav.md-nav');

                            if (togglerLink && submenuToExpand === parentNav) {
                                debugLog('expandActiveTocItem: Expanding parent:', togglerLink.textContent.trim());
                                if (togglerLink.getAttribute('aria-expanded') !== 'true') {
                                    togglerLink.setAttribute('aria-expanded', 'true');
                                    submenuToExpand.style.display = 'block';
                                }
                            }
                            currentElementForExpansion = controllerLi; // Move up to check the controller's parents
                            continue; 
                        }
                    }
                }
                // If not in a recognized collapsible structure, move up from the containing list item.
                // This handles the case where the currentElementForExpansion was the targetTocLink itself,
                // and we now need to check the parents of its containingListItem.
                if (currentElementForExpansion === containingListItem.parentElement) break; // Avoid simple infinite loop
                currentElementForExpansion = containingListItem.parentElement; 
            }
        } else {
            debugLog('expandActiveTocItem: Target TOC link not found for hash:', hash);
        }
    }

    // Initial expansion on page load
    expandActiveTocItem();

    // Expand on hash change
    window.addEventListener('hashchange', expandActiveTocItem);

    // TOC Resizing Logic
    const primarySidebarForResize = document.querySelector('div.md-sidebar.md-sidebar--primary');
    const tocResizer = document.getElementById('toc-resizer');
    const contentArea = document.querySelector('.md-content'); // To potentially adjust its margin

    if (primarySidebarForResize && tocResizer) {
        debugLog('Initializing TOC resizing functionality.');
        let isResizing = false;
        let startX, startWidth;

        // Load saved width from localStorage
        const savedWidth = localStorage.getItem('tocSidebarWidth');
        if (savedWidth) {
            primarySidebarForResize.style.width = savedWidth;
            // If the theme uses flexbox for layout, the content area should adjust automatically.
            // If it uses margins, we might need to adjust md-content's margin-left.
            // For now, let's assume flexbox handles it or the theme's CSS for .md-content
            // is already responsive to .md-sidebar--primary's width.
            debugLog('Loaded sidebar width from localStorage:', savedWidth);
        }

        tocResizer.addEventListener('mousedown', function(e) {
            isResizing = true;
            startX = e.clientX;
            startWidth = parseInt(window.getComputedStyle(primarySidebarForResize).width, 10);
            document.body.style.cursor = 'col-resize'; // Change cursor for the whole body during resize
            primarySidebarForResize.style.userSelect = 'none'; // Prevent text selection during drag
            if (contentArea) contentArea.style.userSelect = 'none';

            debugLog('TOC resize mousedown: startX=', startX, 'startWidth=', startWidth);

            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
        });

        function handleMouseMove(e) {
            if (!isResizing) return;
            const dx = e.clientX - startX;
            let newWidth = startWidth + dx;

            // Enforce min/max width from CSS (or define here if preferred)
            const minWidth = parseInt(window.getComputedStyle(primarySidebarForResize).minWidth, 10) || 150;
            const maxWidth = parseInt(window.getComputedStyle(primarySidebarForResize).maxWidth, 10) || 800;

            if (newWidth < minWidth) newWidth = minWidth;
            if (newWidth > maxWidth) newWidth = maxWidth;

            primarySidebarForResize.style.width = newWidth + 'px';
            // Again, assuming theme handles content reflow. If not, adjust .md-content margin-left here.
            // e.g., if (contentArea) contentArea.style.marginLeft = newWidth + 'px';
            // This depends heavily on how Material for MkDocs structures the main layout.
            // The default Material theme uses flex for .md-container, so changing width of a flex item
            // (.md-sidebar) should make other flex items (.md-main) adjust automatically.
        }

        function handleMouseUp() {
            if (!isResizing) return;
            isResizing = false;
            document.body.style.cursor = 'default';
            primarySidebarForResize.style.userSelect = ''
            if (contentArea) contentArea.style.userSelect = '';

            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);

            // Save the new width to localStorage
            const currentWidth = primarySidebarForResize.style.width;
            localStorage.setItem('tocSidebarWidth', currentWidth);
            debugLog('TOC resize mouseup: new width saved =', currentWidth);
        }
    } else {
        if (!primarySidebarForResize) console.error('Primary sidebar not found for resizing.');
        if (!tocResizer) console.error('TOC resizer element not found.');
    }

    // Persistent attempt to control sidebar scrollwrap height using MutationObserver
    const scrollWrapElementToObserve = document.querySelector('.md-sidebar--primary .md-sidebar__scrollwrap');

    if (scrollWrapElementToObserve) {
        debugLog('Found .md-sidebar__scrollwrap for observation.');

        const ensureScrollWrapCorrectHeight = (element) => {
            const currentInlineHeight = element.style.height;
            if (currentInlineHeight && currentInlineHeight !== 'auto') {
                element.style.height = ''; 
                debugLog('.md-sidebar__scrollwrap inline height (' + currentInlineHeight + ') removed by observer/initial set for scrollWrap.');
            }
        };
        ensureScrollWrapCorrectHeight(scrollWrapElementToObserve);

        const scrollWrapObserver = new MutationObserver((mutationsList) => {
            for (const mutation of mutationsList) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                    debugLog('.md-sidebar__scrollwrap style attribute changed.');
                    ensureScrollWrapCorrectHeight(mutation.target);
                    break; 
                }
            }
        });
        scrollWrapObserver.observe(scrollWrapElementToObserve, { attributes: true });
        debugLog('MutationObserver started for .md-sidebar__scrollwrap style changes.');
    } else {
        console.error('Could not find .md-sidebar__scrollwrap to observe for height adjustments.');
    }

    // New: Observe the primary sidebar itself for inline height/max-height changes
    const primarySidebarElementToObserve = document.querySelector('div.md-sidebar--primary');
    if (primarySidebarElementToObserve) {
        debugLog('Found div.md-sidebar--primary for observation.');

        const ensurePrimarySidebarCorrectHeight = (element) => {
            let modified = false;
            const currentInlineHeight = element.style.height;
            const currentInlineMaxHeight = element.style.maxHeight;

            if (currentInlineHeight && currentInlineHeight !== 'auto') {
                element.style.height = '';
                debugLog('div.md-sidebar--primary inline height (' + currentInlineHeight + ') removed by observer/initial set.');
                modified = true;
            }
            if (currentInlineMaxHeight) { // Any explicit max-height is problematic here
                element.style.maxHeight = '';
                debugLog('div.md-sidebar--primary inline max-height (' + currentInlineMaxHeight + ') removed by observer/initial set.');
                modified = true;
            }
            // If we made changes, it might be good to force a reflow or re-check child dimensions,
            // but usually the browser handles this if CSS is set up correctly.
        };

        ensurePrimarySidebarCorrectHeight(primarySidebarElementToObserve);

        const primarySidebarObserver = new MutationObserver((mutationsList) => {
            for (const mutation of mutationsList) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                    debugLog('div.md-sidebar--primary style attribute changed.');
                    ensurePrimarySidebarCorrectHeight(mutation.target);
                    break;
                }
            }
        });
        primarySidebarObserver.observe(primarySidebarElementToObserve, { attributes: true });
        debugLog('MutationObserver started for div.md-sidebar--primary style changes.');
    } else {
        console.error('Could not find div.md-sidebar--primary to observe for height adjustments.');
    }
}); 
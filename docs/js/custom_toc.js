document.addEventListener('DOMContentLoaded', function () {
    function debugLog(message) {
        console.log(message);
    }

    // Find the active primary navigation item, which should contain the integrated TOC
    const activePrimaryNavItem = document.querySelector('nav.md-nav--primary li.md-nav__item--active');
    debugLog('Active Primary Nav Item:', activePrimaryNavItem);

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
        // Select ALL li.md-nav__item elements within the TOC structure at any depth
        const allNavItems = tocList.querySelectorAll('li.md-nav__item');
        debugLog('Found', allNavItems.length, 'potential nav items in the integrated TOC.');

        allNavItems.forEach((item, index) => {
            // Log details for the first few items to keep console clean
            if (index < 5) { 
                debugLog(`Processing Nav Item ${index}:`, item);
            }

            // Check for direct children: a.md-nav__link and nav.md-nav
            const itemLink = item.querySelector(':scope > a.md-nav__link');
            const nestedNav = item.querySelector(':scope > nav.md-nav');

            if (index < 5) { 
                debugLog(`  Item ${index} Link:`, itemLink);
                debugLog(`  Item ${index} Nested Nav:`, nestedNav);
            }

            if (itemLink && nestedNav) {
                // Check if the nestedNav actually contains a list with items
                const subList = nestedNav.querySelector(':scope > ul.md-nav__list');
                if (!subList || subList.children.length === 0) {
                    if (index < 10) { 
                        debugLog(`  Item ${index} (${itemLink.textContent.trim()}) has no sub-items in its direct nestedNav, skipping toggle.`);
                    }
                    return; // This item doesn't have children to toggle in its own nestedNav
                }
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

                nestedNav.style.display = 'none';
                itemLink.setAttribute('aria-expanded', 'false');

                itemLink.addEventListener('click', function (event) {
                    // Check if the click was specifically on the toggle icon
                    if (event.target.closest('.toc-toggle-icon')) {
                        event.preventDefault(); 
                        event.stopPropagation();

                        const isExpanded = nestedNav.style.display === 'block';
                        nestedNav.style.display = isExpanded ? 'none' : 'block';
                        itemLink.setAttribute('aria-expanded', String(!isExpanded));
                    }
                    // If the click was not on the icon, the default link navigation will proceed
                });
            } else {
                if (index < 10) { // Log for items that don't have the structure to be a parent
                    debugLog(`  Item ${index} (${item.querySelector("a.md-nav__link")?.textContent.trim()}) does not have the direct link/nestedNav structure for toggling.`);
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

}); 
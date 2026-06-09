(function() {
    'use strict';

    var STORAGE_KEY_FAVORITES = 'polymorphic_type_select_favorites';
    var STORAGE_KEY_RECENT = 'polymorphic_type_select_recent';
    var MAX_RECENT_ITEMS = 10;

    function getFavorites() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY_FAVORITES) || '[]');
        } catch (e) {
            return [];
        }
    }

    function setFavorites(favorites) {
        localStorage.setItem(STORAGE_KEY_FAVORITES, JSON.stringify(favorites));
    }

    function getRecent() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY_RECENT) || '[]');
        } catch (e) {
            return [];
        }
    }

    function setRecent(recent) {
        localStorage.setItem(STORAGE_KEY_RECENT, JSON.stringify(recent));
    }

    function addRecent(id) {
        var recent = getRecent();
        recent = recent.filter(function(item) { return item !== id; });
        recent.unshift(id);
        if (recent.length > MAX_RECENT_ITEMS) {
            recent = recent.slice(0, MAX_RECENT_ITEMS);
        }
        setRecent(recent);
    }

    function toggleFavorite(id) {
        var favorites = getFavorites();
        var index = favorites.indexOf(id);
        if (index === -1) {
            favorites.push(id);
        } else {
            favorites.splice(index, 1);
        }
        setFavorites(favorites);
        return index === -1;
    }

    function isFavorite(id) {
        return getFavorites().indexOf(id) !== -1;
    }

    function initWidget(container) {
        var hiddenInput = container.querySelector('[data-polymorphic-type-input]');
        var searchInput = container.querySelector('[data-polymorphic-search]');
        var tabsContainer = container.querySelector('[data-polymorphic-tabs]');
        var categoriesContainer = container.querySelector('[data-polymorphic-categories]');
        var submitButton = container.querySelector('[data-polymorphic-submit]');
        var typeDataUrl = container.getAttribute('data-type-data-url');
        var selectedTypeId = null;
        var allCategories = [];
        var loadingEl = container.querySelector('.polymorphic-type-select__loading');

        function renderCategories(categories, filter, tab) {
            var searchTerm = (filter || '').toLowerCase();
            var favorites = getFavorites();
            var recent = getRecent();
            var html = '';

            var filteredCategories = [];
            for (var c = 0; c < categories.length; c++) {
                var category = categories[c];
                var filteredTypes = [];
                for (var t = 0; t < category.types.length; t++) {
                    var type = category.types[t];
                    var name = (type.name || '').toLowerCase();

                    if (tab === 'favorites' && favorites.indexOf(type.id) === -1) {
                        continue;
                    }
                    if (tab === 'recent' && recent.indexOf(type.id) === -1) {
                        continue;
                    }
                    if (searchTerm && name.indexOf(searchTerm) === -1) {
                        continue;
                    }
                    filteredTypes.push(type);
                }
                if (filteredTypes.length > 0) {
                    filteredCategories.push({
                        name: category.name,
                        types: filteredTypes
                    });
                }
            }

            if (filteredCategories.length === 0) {
                html = '<div class="polymorphic-type-select__empty">' +
                    gettext('No types found.') + '</div>';
            } else {
                for (var i = 0; i < filteredCategories.length; i++) {
                    var cat = filteredCategories[i];
                    html += '<div class="polymorphic-type-select__category">';
                    html += '<h3 class="polymorphic-type-select__category-name">' +
                        escapeHtml(cat.name) + '</h3>';
                    html += '<div class="polymorphic-type-select__type-list">';
                    for (var j = 0; j < cat.types.length; j++) {
                        var tpe = cat.types[j];
                        var favClass = isFavorite(tpe.id) ? 'is-favorite' : '';
                        var selectedClass = selectedTypeId === tpe.id ? 'is-selected' : '';
                        html += '<div class="polymorphic-type-select__type-item ' +
                            favClass + ' ' + selectedClass +
                            '" data-type-id="' + tpe.id + '">';
                        html += '<div class="polymorphic-type-select__type-info">';
                        html += '<span class="polymorphic-type-select__type-name">' +
                            escapeHtml(tpe.name) + '</span>';
                        if (tpe.docstring) {
                            html += '<span class="polymorphic-type-select__type-desc">' +
                                escapeHtml(tpe.docstring) + '</span>';
                        }
                        html += '</div>';
                        html += '<button type="button" class="polymorphic-type-select__fav-btn" ' +
                            'data-fav-id="' + tpe.id + '" title="' +
                            gettext('Toggle favorite') + '">';
                        html += isFavorite(tpe.id) ? '&#9733;' : '&#9734;';
                        html += '</button>';
                        html += '</div>';
                    }
                    html += '</div></div>';
                }
            }

            categoriesContainer.innerHTML = html;

            var typeItems = categoriesContainer.querySelectorAll('.polymorphic-type-select__type-item');
            for (var k = 0; k < typeItems.length; k++) {
                typeItems[k].addEventListener('click', function(e) {
                    if (e.target.closest('.polymorphic-type-select__fav-btn')) {
                        return;
                    }
                    var typeId = parseInt(this.getAttribute('data-type-id'), 10);
                    selectType(typeId);
                });
            }

            var favButtons = categoriesContainer.querySelectorAll('.polymorphic-type-select__fav-btn');
            for (var m = 0; m < favButtons.length; m++) {
                favButtons[m].addEventListener('click', function(e) {
                    e.stopPropagation();
                    var favId = parseInt(this.getAttribute('data-fav-id'), 10);
                    var added = toggleFavorite(favId);
                    this.innerHTML = added ? '&#9733;' : '&#9734;';
                    var parentItem = this.closest('.polymorphic-type-select__type-item');
                    if (added) {
                        parentItem.classList.add('is-favorite');
                    } else {
                        parentItem.classList.remove('is-favorite');
                    }
                });
            }
        }

        function selectType(typeId) {
            selectedTypeId = typeId;
            hiddenInput.value = typeId;
            submitButton.disabled = false;

            var allItems = categoriesContainer.querySelectorAll(
                '.polymorphic-type-select__type-item');
            for (var i = 0; i < allItems.length; i++) {
                var itemTypeId = parseInt(allItems[i].getAttribute('data-type-id'), 10);
                if (itemTypeId === typeId) {
                    allItems[i].classList.add('is-selected');
                } else {
                    allItems[i].classList.remove('is-selected');
                }
            }
        }

        function switchTab(tabName) {
            var tabs = tabsContainer.querySelectorAll('.polymorphic-type-select__tab');
            for (var i = 0; i < tabs.length; i++) {
                tabs[i].classList.remove('active');
            }
            var activeTab = tabsContainer.querySelector('[data-tab="' + tabName + '"]');
            if (activeTab) {
                activeTab.classList.add('active');
            }
            renderCategories(allCategories, searchInput.value, tabName);
        }

        function escapeHtml(text) {
            var div = document.createElement('div');
            div.appendChild(document.createTextNode(text));
            return div.innerHTML;
        }

        function gettext(text) {
            return text;
        }

        function loadTypes() {
            fetch(typeDataUrl, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(function(response) {
                if (!response.ok) {
                    throw new Error('Failed to load types');
                }
                return response.json();
            })
            .then(function(data) {
                allCategories = data.categories || [];
                renderCategories(allCategories, '', 'all');
            })
            .catch(function(error) {
                categoriesContainer.innerHTML =
                    '<div class="polymorphic-type-select__error">' +
                    gettext('Failed to load types. Please try again.') +
                    '</div>';
            });
        }

        searchInput.addEventListener('input', function() {
            var activeTab = tabsContainer.querySelector('.polymorphic-type-select__tab.active');
            var tabName = activeTab ? activeTab.getAttribute('data-tab') : 'all';
            renderCategories(allCategories, this.value, tabName);
        });

        var tabs = tabsContainer.querySelectorAll('.polymorphic-type-select__tab');
        for (var i = 0; i < tabs.length; i++) {
            tabs[i].addEventListener('click', function() {
                switchTab(this.getAttribute('data-tab'));
            });
        }

        submitButton.addEventListener('click', function(e) {
            if (!selectedTypeId) {
                e.preventDefault();
                return;
            }
            addRecent(selectedTypeId);
        });

        loadTypes();
    }

    document.addEventListener('DOMContentLoaded', function() {
        var containers = document.querySelectorAll('.polymorphic-type-select');
        for (var i = 0; i < containers.length; i++) {
            initWidget(containers[i]);
        }
    });

    if (document.readyState !== 'loading') {
        var containers = document.querySelectorAll('.polymorphic-type-select');
        for (var i = 0; i < containers.length; i++) {
            initWidget(containers[i]);
        }
    }
})();
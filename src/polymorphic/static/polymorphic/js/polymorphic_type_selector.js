(function() {
    'use strict';

    var PolymorphicTypeSelector = function(container, options) {
        this.container = container;
        this.api_url = options.api_url || '';
        this.toggle_favorite_url = options.toggle_favorite_url || '';
        this.extra_qs = options.extra_qs || '';
        this.types_data = options.types_data || {
            all_types: [],
            groups: [],
            favorites: [],
            recent: []
        };
        this.csrf_token = options.csrf_token || '';
        this.current_tab = 'all';
        this.search_query = '';
        this.search_debounce_timer = null;
        this.SEARCH_DEBOUNCE_MS = 200;
        this.ASYNC_LOAD_DELAY_MS = 50;

        this.init();
    };

    PolymorphicTypeSelector.prototype.init = function() {
        this.render();
        this.bindEvents();
    };

    PolymorphicTypeSelector.prototype.render = function() {
        this.container.innerHTML = '';
        this.container.classList.add('polymorphic-type-selector');

        var search_box = this.renderSearchBox();
        var tabs = this.renderTabs();
        var content = this.renderContent();

        this.container.appendChild(search_box);
        this.container.appendChild(tabs);
        this.container.appendChild(content);
    };

    PolymorphicTypeSelector.prototype.renderSearchBox = function() {
        var box = document.createElement('div');
        box.className = 'pts-search-box';

        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'pts-search-input';
        input.placeholder = gettext ? gettext('Search types...') : 'Search types...';
        input.setAttribute('aria-label', 'Search types');

        var icon = document.createElement('span');
        icon.className = 'pts-search-icon';
        icon.innerHTML = '&#128269;';

        box.appendChild(icon);
        box.appendChild(input);
        this._search_input = input;
        return box;
    };

    PolymorphicTypeSelector.prototype.renderTabs = function() {
        var nav = document.createElement('div');
        nav.className = 'pts-tabs';

        var tabs = [
            {id: 'all', label: 'All'},
            {id: 'recent', label: 'Recent'},
            {id: 'favorites', label: 'Favorites'},
            {id: 'categories', label: 'Categories'}
        ];

        var self = this;
        tabs.forEach(function(tab) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'pts-tab' + (tab.id === self.current_tab ? ' pts-tab-active' : '');
            btn.setAttribute('data-tab', tab.id);
            btn.textContent = tab.label;
            nav.appendChild(btn);
        });

        this._tabs_nav = nav;
        return nav;
    };

    PolymorphicTypeSelector.prototype.renderContent = function() {
        var content = document.createElement('div');
        content.className = 'pts-content';
        this._content = content;
        this.updateContent();
        return content;
    };

    PolymorphicTypeSelector.prototype.updateContent = function() {
        this._content.innerHTML = '';

        switch (this.current_tab) {
            case 'all':
                this.renderAllTypes();
                break;
            case 'recent':
                this.renderRecentTypes();
                break;
            case 'favorites':
                this.renderFavoriteTypes();
                break;
            case 'categories':
                this.renderCategorizedTypes();
                break;
        }
    };

    PolymorphicTypeSelector.prototype.renderAllTypes = function() {
        var types = this.types_data.all_types;
        if (this.search_query) {
            types = this.filterTypes(types, this.search_query);
        }

        if (types.length === 0) {
            this.renderEmptyState();
            return;
        }

        var list = this.createTypeList(types);
        this._content.appendChild(list);
    };

    PolymorphicTypeSelector.prototype.renderRecentTypes = function() {
        var types = this.types_data.recent;
        if (this.search_query) {
            types = this.filterTypes(types, this.search_query);
        }

        if (types.length === 0) {
            this.renderEmptyState('No recently used types.');
            return;
        }

        var list = this.createTypeList(types);
        this._content.appendChild(list);
    };

    PolymorphicTypeSelector.prototype.renderFavoriteTypes = function() {
        var types = this.types_data.favorites;
        if (this.search_query) {
            types = this.filterTypes(types, this.search_query);
        }

        if (types.length === 0) {
            this.renderEmptyState('No favorite types. Click the star icon to add favorites.');
            return;
        }

        var list = this.createTypeList(types);
        this._content.appendChild(list);
    };

    PolymorphicTypeSelector.prototype.renderCategorizedTypes = function() {
        var groups = this.types_data.groups;
        if (this.search_query) {
            groups = this.filterGroups(groups, this.search_query);
        }

        if (groups.length === 0) {
            this.renderEmptyState();
            return;
        }

        var self = this;
        groups.forEach(function(group) {
            var section = document.createElement('div');
            section.className = 'pts-category-section';

            var header = document.createElement('h3');
            header.className = 'pts-category-header';
            header.textContent = group.label;
            section.appendChild(header);

            var list = self.createTypeList(group.models);
            section.appendChild(list);
            self._content.appendChild(section);
        });
    };

    PolymorphicTypeSelector.prototype.createTypeList = function(types) {
        var list = document.createElement('ul');
        list.className = 'pts-type-list';

        var self = this;
        var favorites = this.types_data.favorites.map(function(f) { return f.ct_id; });

        types.forEach(function(type_info) {
            var item = document.createElement('li');
            item.className = 'pts-type-item';
            item.setAttribute('data-ct-id', type_info.ct_id);

            var link = document.createElement('a');
            link.href = '?ct_id=' + type_info.ct_id + self.extra_qs;
            link.className = 'pts-type-link';
            link.textContent = type_info.name;

            var fav_btn = document.createElement('button');
            fav_btn.type = 'button';
            fav_btn.className = 'pts-fav-btn' + (favorites.indexOf(type_info.ct_id) >= 0 ? ' pts-fav-active' : '');
            fav_btn.setAttribute('data-ct-id', type_info.ct_id);
            fav_btn.setAttribute('aria-label', 'Toggle favorite');
            fav_btn.title = favorites.indexOf(type_info.ct_id) >= 0 ? 'Remove from favorites' : 'Add to favorites';
            fav_btn.innerHTML = favorites.indexOf(type_info.ct_id) >= 0 ? '&#9733;' : '&#9734;';

            item.appendChild(fav_btn);
            item.appendChild(link);
            list.appendChild(item);
        });

        return list;
    };

    PolymorphicTypeSelector.prototype.renderEmptyState = function(message) {
        var empty = document.createElement('div');
        empty.className = 'pts-empty-state';
        empty.textContent = message || 'No types found.';
        this._content.appendChild(empty);
    };

    PolymorphicTypeSelector.prototype.filterTypes = function(types, query) {
        var q = query.toLowerCase();
        return types.filter(function(t) {
            return t.name.toLowerCase().indexOf(q) >= 0 || t.model_name.toLowerCase().indexOf(q) >= 0;
        });
    };

    PolymorphicTypeSelector.prototype.filterGroups = function(groups, query) {
        var q = query.toLowerCase();
        var result = [];
        groups.forEach(function(group) {
            var filtered_models = group.models.filter(function(m) {
                return m.name.toLowerCase().indexOf(q) >= 0 || m.model_name.toLowerCase().indexOf(q) >= 0;
            });
            if (filtered_models.length > 0) {
                result.push({label: group.label, models: filtered_models});
            }
        });
        return result;
    };

    PolymorphicTypeSelector.prototype.bindEvents = function() {
        var self = this;

        if (this._search_input) {
            this._search_input.addEventListener('input', function(e) {
                clearTimeout(self.search_debounce_timer);
                self.search_debounce_timer = setTimeout(function() {
                    self.search_query = e.target.value.trim();
                    self.updateContent();
                }, self.SEARCH_DEBOUNCE_MS);
            });
        }

        if (this._tabs_nav) {
            this._tabs_nav.addEventListener('click', function(e) {
                var btn = e.target.closest('.pts-tab');
                if (!btn) return;
                var tab_id = btn.getAttribute('data-tab');
                if (tab_id === self.current_tab) return;

                self.current_tab = tab_id;
                var all_tabs = self._tabs_nav.querySelectorAll('.pts-tab');
                all_tabs.forEach(function(t) { t.classList.remove('pts-tab-active'); });
                btn.classList.add('pts-tab-active');
                self.updateContent();
            });
        }

        this.container.addEventListener('click', function(e) {
            var fav_btn = e.target.closest('.pts-fav-btn');
            if (fav_btn) {
                e.preventDefault();
                e.stopPropagation();
                var ct_id = parseInt(fav_btn.getAttribute('data-ct-id'), 10);
                self.toggleFavorite(ct_id, fav_btn);
            }
        });
    };

    PolymorphicTypeSelector.prototype.toggleFavorite = function(ct_id, btn_element) {
        var self = this;
        var url = this.toggle_favorite_url + ct_id + '/';

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.csrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin'
        }).then(function(response) {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        }).then(function(data) {
            if (data.is_favorite) {
                btn_element.classList.add('pts-fav-active');
                btn_element.innerHTML = '&#9733;';
                btn_element.title = 'Remove from favorites';
            } else {
                btn_element.classList.remove('pts-fav-active');
                btn_element.innerHTML = '&#9734;';
                btn_element.title = 'Add to favorites';
            }
            self.loadTypesDataAsync();
        }).catch(function(err) {
            console.error('Failed to toggle favorite:', err);
        });
    };

    PolymorphicTypeSelector.prototype.loadTypesDataAsync = function(search_query) {
        var self = this;
        var url = this.api_url;
        if (search_query) {
            url += (url.indexOf('?') >= 0 ? '&' : '?') + 'search=' + encodeURIComponent(search_query);
        }

        fetch(url, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        }).then(function(response) {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        }).then(function(data) {
            self.types_data = data;
            self.updateContent();
        }).catch(function(err) {
            console.error('Failed to load types data:', err);
        });
    };

    PolymorphicTypeSelector.prototype.initAsync = function() {
        var self = this;
        this.container.classList.add('pts-loading');

        setTimeout(function() {
            self.loadTypesDataAsync();
            self.container.classList.remove('pts-loading');
        }, self.ASYNC_LOAD_DELAY_MS);
    };

    if (typeof window !== 'undefined') {
        window.PolymorphicTypeSelector = PolymorphicTypeSelector;
    }

    function initPolymorphicTypeSelectors() {
        var elements = document.querySelectorAll('[data-polymorphic-type-selector]');
        elements.forEach(function(el) {
            var options = {};
            try {
                options = JSON.parse(el.getAttribute('data-pts-options') || '{}');
            } catch (e) {
                console.error('Failed to parse polymorphic type selector options:', e);
            }

            var selector = new PolymorphicTypeSelector(el, options);

            if (el.getAttribute('data-pts-async') === 'true') {
                selector.initAsync();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPolymorphicTypeSelectors);
    } else {
        initPolymorphicTypeSelectors();
    }
})();

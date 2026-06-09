(function() {
    function parseStoredIds(key) {
        try {
            const value = window.localStorage.getItem(key);
            if (!value) {
                return [];
            }
            const parsed = JSON.parse(value);
            if (!Array.isArray(parsed)) {
                return [];
            }
            return parsed.map(String);
        } catch (error) {
            return [];
        }
    }

    function storeIds(key, ids) {
        try {
            window.localStorage.setItem(key, JSON.stringify(ids));
        } catch (error) {
            return;
        }
    }

    function debounce(callback, delay) {
        let timer = null;
        return function() {
            window.clearTimeout(timer);
            timer = window.setTimeout(() => callback.apply(this, arguments), delay);
        };
    }

    function initTypeSelector(selector) {
        const searchInput = selector.querySelector("[data-role='search']");
        const statusNode = selector.querySelector("[data-role='status']");
        const sectionsNode = selector.querySelector("[data-role='sections']");
        const form = selector.closest("form");
        const favoritesKey = `${selector.dataset.storageKey}:favorites`;
        const recentKey = `${selector.dataset.storageKey}:recent`;
        const radioSelector = "input[name='ct_id']";
        let selectedId = selector.dataset.initialCtId || "";
        let results = [];
        let fetchToken = 0;

        if (!searchInput || !statusNode || !sectionsNode || !form) {
            return;
        }

        function getRadioInputs() {
            return Array.from(document.querySelectorAll(radioSelector));
        }

        function getSelectedRadioId() {
            const checked = getRadioInputs().find((radio) => radio.checked);
            return checked ? checked.value : "";
        }

        function setSelectedRadio(id) {
            getRadioInputs().forEach((radio) => {
                radio.checked = radio.value === id;
            });
        }

        function hideFallbackFieldset() {
            getRadioInputs().forEach((radio) => {
                const row = radio.closest(".form-row");
                const fieldset = radio.closest("fieldset");
                if (row) {
                    row.hidden = true;
                }
                if (fieldset && fieldset.querySelectorAll(".form-row").length === 1) {
                    fieldset.hidden = true;
                }
            });
        }

        function updateStatus(message) {
            statusNode.textContent = message;
        }

        function getFavorites() {
            return parseStoredIds(favoritesKey);
        }

        function setFavorites(ids) {
            storeIds(favoritesKey, Array.from(new Set(ids)));
        }

        function getRecent() {
            return parseStoredIds(recentKey);
        }

        function pushRecent(id) {
            const ids = getRecent().filter((item) => item !== id);
            ids.unshift(id);
            storeIds(recentKey, ids.slice(0, 5));
        }

        function groupByCategory(items) {
            return items.reduce((groups, item) => {
                const group = groups[item.category] || [];
                group.push(item);
                groups[item.category] = group;
                return groups;
            }, {});
        }

        function createOption(item) {
            const option = document.createElement("div");
            option.className = "polymorphic-type-selector__option";
            option.dataset.ctId = String(item.ct_id);
            if (String(item.ct_id) === selectedId) {
                option.classList.add("is-selected");
            }

            const selectButton = document.createElement("button");
            selectButton.type = "button";
            selectButton.className = "polymorphic-type-selector__select";
            selectButton.dataset.role = "select";
            selectButton.setAttribute("aria-label", `${selector.dataset.selectLabel}: ${item.label}`);
            selectButton.addEventListener("click", () => {
                selectedId = String(item.ct_id);
                setSelectedRadio(selectedId);
                renderSections(results);
            });

            const name = document.createElement("span");
            name.className = "polymorphic-type-selector__name";
            name.textContent = item.label;

            const meta = document.createElement("span");
            meta.className = "polymorphic-type-selector__meta";
            meta.textContent = `${item.category} · ${item.object_name}`;

            selectButton.appendChild(name);
            selectButton.appendChild(meta);
            option.appendChild(selectButton);

            const favoriteButton = document.createElement("button");
            favoriteButton.type = "button";
            favoriteButton.className = "polymorphic-type-selector__favorite";
            favoriteButton.dataset.role = "favorite";
            favoriteButton.textContent = "★";

            const favoriteIds = getFavorites();
            const isFavorite = favoriteIds.includes(String(item.ct_id));
            if (isFavorite) {
                favoriteButton.classList.add("is-favorite");
                favoriteButton.setAttribute("aria-label", selector.dataset.favoriteRemoveLabel);
                favoriteButton.title = selector.dataset.favoriteRemoveLabel;
            } else {
                favoriteButton.setAttribute("aria-label", selector.dataset.favoriteAddLabel);
                favoriteButton.title = selector.dataset.favoriteAddLabel;
            }

            favoriteButton.addEventListener("click", () => {
                const itemId = String(item.ct_id);
                const updatedFavorites = getFavorites();
                const index = updatedFavorites.indexOf(itemId);
                if (index >= 0) {
                    updatedFavorites.splice(index, 1);
                } else {
                    updatedFavorites.unshift(itemId);
                }
                setFavorites(updatedFavorites);
                renderSections(results);
            });

            option.appendChild(favoriteButton);
            return option;
        }

        function createSection(title, items, sectionName) {
            if (!items.length) {
                return null;
            }

            const section = document.createElement("section");
            section.className = "polymorphic-type-selector__section";
            section.dataset.section = sectionName;

            const header = document.createElement("h2");
            header.className = "polymorphic-type-selector__section-header";
            header.textContent = title;
            section.appendChild(header);

            const body = document.createElement("div");
            body.className = "polymorphic-type-selector__section-body";
            const options = document.createElement("div");
            options.className = "polymorphic-type-selector__options";
            items.forEach((item) => options.appendChild(createOption(item)));
            body.appendChild(options);
            section.appendChild(body);
            return section;
        }

        function createCategorizedSection(items) {
            if (!items.length) {
                return null;
            }

            const section = document.createElement("section");
            section.className = "polymorphic-type-selector__section";
            section.dataset.section = "categories";

            const header = document.createElement("h2");
            header.className = "polymorphic-type-selector__section-header";
            header.textContent = selector.dataset.categoriesLabel || selector.dataset.allTypesLabel;
            section.appendChild(header);

            const body = document.createElement("div");
            body.className = "polymorphic-type-selector__section-body";
            const grouped = groupByCategory(items);

            Object.keys(grouped).sort().forEach((category) => {
                const group = document.createElement("div");
                group.className = "polymorphic-type-selector__category-group";

                const title = document.createElement("h3");
                title.className = "polymorphic-type-selector__category-title";
                title.textContent = category;
                group.appendChild(title);

                const options = document.createElement("div");
                options.className = "polymorphic-type-selector__options";
                grouped[category].forEach((item) => options.appendChild(createOption(item)));
                group.appendChild(options);
                body.appendChild(group);
            });

            section.appendChild(body);
            return section;
        }

        function renderSections(items) {
            sectionsNode.innerHTML = "";
            const itemMap = new Map(items.map((item) => [String(item.ct_id), item]));
            const favorites = getFavorites().map((id) => itemMap.get(id)).filter(Boolean);
            const recent = getRecent().map((id) => itemMap.get(id)).filter(Boolean);
            const fragments = [
                createSection(selector.dataset.favoritesLabel, favorites, "favorites"),
                createSection(selector.dataset.recentLabel, recent, "recent"),
                createCategorizedSection(items),
            ].filter(Boolean);

            if (!fragments.length) {
                const empty = document.createElement("div");
                empty.className = "polymorphic-type-selector__empty";
                empty.textContent = selector.dataset.emptyLabel;
                sectionsNode.appendChild(empty);
                return;
            }

            fragments.forEach((fragment) => sectionsNode.appendChild(fragment));
        }

        function applyResults(newResults) {
            results = newResults;
            const currentRadioId = getSelectedRadioId();
            if (currentRadioId) {
                selectedId = currentRadioId;
            } else if (!results.find((item) => String(item.ct_id) === selectedId) && results.length) {
                selectedId = String(results[0].ct_id);
                setSelectedRadio(selectedId);
            } else if (selectedId) {
                setSelectedRadio(selectedId);
            }

            renderSections(results);
            updateStatus(results.length ? "" : selector.dataset.emptyLabel);
            selector.classList.add("is-active");
            hideFallbackFieldset();
        }

        function renderError() {
            selector.classList.add("is-active");
            sectionsNode.innerHTML = "";
            const error = document.createElement("div");
            error.className = "polymorphic-type-selector__error";
            error.textContent = selector.dataset.errorLabel;
            sectionsNode.appendChild(error);
            updateStatus(selector.dataset.errorLabel);
        }

        function fetchResults(query) {
            fetchToken += 1;
            const token = fetchToken;
            updateStatus(selector.dataset.loadingLabel);
            const requestUrl = new URL(selector.dataset.fetchUrl, window.location.origin);
            const currentUrl = new URL(window.location.href);

            currentUrl.searchParams.forEach((value, key) => {
                if (key !== "q") {
                    requestUrl.searchParams.set(key, value);
                }
            });
            if (query) {
                requestUrl.searchParams.set("q", query);
            }

            window.fetch(requestUrl.toString(), {
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
                credentials: "same-origin",
            })
                .then((response) => {
                    if (!response.ok) {
                        throw new Error(`Request failed with status ${response.status}`);
                    }
                    return response.json();
                })
                .then((payload) => {
                    if (token !== fetchToken) {
                        return;
                    }
                    applyResults(payload.results || []);
                })
                .catch(() => {
                    if (token !== fetchToken) {
                        return;
                    }
                    renderError();
                });
        }

        form.addEventListener("submit", () => {
            const currentId = getSelectedRadioId() || selectedId;
            if (currentId) {
                pushRecent(currentId);
            }
        });

        form.addEventListener("change", (event) => {
            const target = event.target;
            if (target && target.matches && target.matches(radioSelector)) {
                selectedId = target.value;
                renderSections(results);
            }
        });

        searchInput.addEventListener("input", debounce((event) => {
            fetchResults(event.target.value.trim());
        }, 150));

        fetchResults("");
    }

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll(".polymorphic-type-selector").forEach(initTypeSelector);
    });
})();

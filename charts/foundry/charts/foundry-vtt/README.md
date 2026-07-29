# Foundry VTT

<!-- BADGES/ -->

[![FoundryVTT Version: v0.7.10](https://img.shields.io/badge/foundry-v0.7.10-brightgreen?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAAAXNSR0IArs4c6QAAAIRlWElmTU0AKgAAAAgABQESAAMAAAABAAEAAAEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIAAIdpAAQAAAABAAAAWgAAAAAAAABIAAAAAQAAAEgAAAABAAOgAQADAAAAAQABAACgAgAEAAAAAQAAAA6gAwAEAAAAAQAAAA4AAAAATspU+QAAAAlwSFlzAAALEwAACxMBAJqcGAAAAVlpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IlhNUCBDb3JlIDUuNC4wIj4KICAgPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICAgICAgPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIKICAgICAgICAgICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iPgogICAgICAgICA8dGlmZjpPcmllbnRhdGlvbj4xPC90aWZmOk9yaWVudGF0aW9uPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KTMInWQAAAiFJREFUKBVVks1rE1EUxc+d5tO0prZVSZsUhSBIPyC02ooWurJ0I7rQlRvdC/4N4h9gt7pyoRTswpWgILgQBIOIiC340VhbpC0Ek85MGmPmXc+baWpNGJg77/7uOffeB+z9FHB0FrH9eLwwqpOF0f34KrpsTicW+6L8KE8QhO/n8n1IOgtQHYZA+a/Ai9+Wd6v1g7liq5A2OjKSQNa9hkO4hAzOIylf6CHALk6hoWXsylPkfjyyApaJhVCxmERy5zLSuI7D8h1H5BWht1aBhS6wdI3pN7GabyuyS4JPrchzujmNjDxAVrrRL2PoxRSGxOfjssgEjkkJvVJBWu6h5M7YenvDoOO0OgicD4TPIKWbBG6xvwTaKCMwSU7hKxK6gt8mbsFIMaF5iDyjUg6iPnqc58higCr9fD4iTvWMziAmK2g73f/AADVWX0YXrlChirgOcqL3WXYBYpTfUuxzjkW30dI1C0ZW1RnjMopo4C56MIs6CgQrMER2cJoz9zjdO2iz17g2yZUjqzHWbuA4/ugiEz7DVRe/aLxmcvDQ5Cq+oWGWeDbAgiETXgArrVOFGzR0EkclxrVMcpfLgFThY5roe2yz95ZZkzcbj22+w2VG8Pz6Q/b5Gr6uM9mw04uo6ll4tOlhE8a8xNzGYihCJoT+u3I4kUIp6OM0X9CHHds8frbqsrXlh9CB62nj8L5a9Y4DHR/K68TgcHhoz607Qp34L72X0rdSdM+vAAAAAElFTkSuQmCC)](https://foundryvtt.com/releases/0.7.10)
[![FoundryVTT Version: v0.8.9](https://img.shields.io/badge/foundry-v0.8.9-brightgreen?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAAAXNSR0IArs4c6QAAAIRlWElmTU0AKgAAAAgABQESAAMAAAABAAEAAAEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIAAIdpAAQAAAABAAAAWgAAAAAAAABIAAAAAQAAAEgAAAABAAOgAQADAAAAAQABAACgAgAEAAAAAQAAAA6gAwAEAAAAAQAAAA4AAAAATspU+QAAAAlwSFlzAAALEwAACxMBAJqcGAAAAVlpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IlhNUCBDb3JlIDUuNC4wIj4KICAgPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICAgICAgPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIKICAgICAgICAgICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iPgogICAgICAgICA8dGlmZjpPcmllbnRhdGlvbj4xPC90aWZmOk9yaWVudGF0aW9uPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KTMInWQAAAiFJREFUKBVVks1rE1EUxc+d5tO0prZVSZsUhSBIPyC02ooWurJ0I7rQlRvdC/4N4h9gt7pyoRTswpWgILgQBIOIiC340VhbpC0Ek85MGmPmXc+baWpNGJg77/7uOffeB+z9FHB0FrH9eLwwqpOF0f34KrpsTicW+6L8KE8QhO/n8n1IOgtQHYZA+a/Ai9+Wd6v1g7liq5A2OjKSQNa9hkO4hAzOIylf6CHALk6hoWXsylPkfjyyApaJhVCxmERy5zLSuI7D8h1H5BWht1aBhS6wdI3pN7GabyuyS4JPrchzujmNjDxAVrrRL2PoxRSGxOfjssgEjkkJvVJBWu6h5M7YenvDoOO0OgicD4TPIKWbBG6xvwTaKCMwSU7hKxK6gt8mbsFIMaF5iDyjUg6iPnqc58higCr9fD4iTvWMziAmK2g73f/AADVWX0YXrlChirgOcqL3WXYBYpTfUuxzjkW30dI1C0ZW1RnjMopo4C56MIs6CgQrMER2cJoz9zjdO2iz17g2yZUjqzHWbuA4/ugiEz7DVRe/aLxmcvDQ5Cq+oWGWeDbAgiETXgArrVOFGzR0EkclxrVMcpfLgFThY5roe2yz95ZZkzcbj22+w2VG8Pz6Q/b5Gr6uM9mw04uo6ll4tOlhE8a8xNzGYihCJoT+u3I4kUIp6OM0X9CHHds8frbqsrXlh9CB62nj8L5a9Y4DHR/K68TgcHhoz607Qp34L72X0rdSdM+vAAAAAElFTkSuQmCC)](https://foundryvtt.com/releases/0.8.9)
[![FoundryVTT Version: v9.280](https://img.shields.io/badge/foundry-v9.269-brightgreen?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAAAXNSR0IArs4c6QAAAIRlWElmTU0AKgAAAAgABQESAAMAAAABAAEAAAEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIAAIdpAAQAAAABAAAAWgAAAAAAAABIAAAAAQAAAEgAAAABAAOgAQADAAAAAQABAACgAgAEAAAAAQAAAA6gAwAEAAAAAQAAAA4AAAAATspU+QAAAAlwSFlzAAALEwAACxMBAJqcGAAAAVlpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IlhNUCBDb3JlIDUuNC4wIj4KICAgPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICAgICAgPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIKICAgICAgICAgICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iPgogICAgICAgICA8dGlmZjpPcmllbnRhdGlvbj4xPC90aWZmOk9yaWVudGF0aW9uPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KTMInWQAAAiFJREFUKBVVks1rE1EUxc+d5tO0prZVSZsUhSBIPyC02ooWurJ0I7rQlRvdC/4N4h9gt7pyoRTswpWgILgQBIOIiC340VhbpC0Ek85MGmPmXc+baWpNGJg77/7uOffeB+z9FHB0FrH9eLwwqpOF0f34KrpsTicW+6L8KE8QhO/n8n1IOgtQHYZA+a/Ai9+Wd6v1g7liq5A2OjKSQNa9hkO4hAzOIylf6CHALk6hoWXsylPkfjyyApaJhVCxmERy5zLSuI7D8h1H5BWht1aBhS6wdI3pN7GabyuyS4JPrchzujmNjDxAVrrRL2PoxRSGxOfjssgEjkkJvVJBWu6h5M7YenvDoOO0OgicD4TPIKWbBG6xvwTaKCMwSU7hKxK6gt8mbsFIMaF5iDyjUg6iPnqc58higCr9fD4iTvWMziAmK2g73f/AADVWX0YXrlChirgOcqL3WXYBYpTfUuxzjkW30dI1C0ZW1RnjMopo4C56MIs6CgQrMER2cJoz9zjdO2iz17g2yZUjqzHWbuA4/ugiEz7DVRe/aLxmcvDQ5Cq+oWGWeDbAgiETXgArrVOFGzR0EkclxrVMcpfLgFThY5roe2yz95ZZkzcbj22+w2VG8Pz6Q/b5Gr6uM9mw04uo6ll4tOlhE8a8xNzGYihCJoT+u3I4kUIp6OM0X9CHHds8frbqsrXlh9CB62nj8L5a9Y4DHR/K68TgcHhoz607Qp34L72X0rdSdM+vAAAAAElFTkSuQmCC)](https://foundryvtt.com/releases/9.280)
[![FoundryVTT Version: v10.303](https://img.shields.io/badge/foundry-v10.303-brightgreen?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAAAXNSR0IArs4c6QAAAIRlWElmTU0AKgAAAAgABQESAAMAAAABAAEAAAEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIAAIdpAAQAAAABAAAAWgAAAAAAAABIAAAAAQAAAEgAAAABAAOgAQADAAAAAQABAACgAgAEAAAAAQAAAA6gAwAEAAAAAQAAAA4AAAAATspU+QAAAAlwSFlzAAALEwAACxMBAJqcGAAAAVlpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IlhNUCBDb3JlIDUuNC4wIj4KICAgPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICAgICAgPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIKICAgICAgICAgICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iPgogICAgICAgICA8dGlmZjpPcmllbnRhdGlvbj4xPC90aWZmOk9yaWVudGF0aW9uPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KTMInWQAAAiFJREFUKBVVks1rE1EUxc+d5tO0prZVSZsUhSBIPyC02ooWurJ0I7rQlRvdC/4N4h9gt7pyoRTswpWgILgQBIOIiC340VhbpC0Ek85MGmPmXc+baWpNGJg77/7uOffeB+z9FHB0FrH9eLwwqpOF0f34KrpsTicW+6L8KE8QhO/n8n1IOgtQHYZA+a/Ai9+Wd6v1g7liq5A2OjKSQNa9hkO4hAzOIylf6CHALk6hoWXsylPkfjyyApaJhVCxmERy5zLSuI7D8h1H5BWht1aBhS6wdI3pN7GabyuyS4JPrchzujmNjDxAVrrRL2PoxRSGxOfjssgEjkkJvVJBWu6h5M7YenvDoOO0OgicD4TPIKWbBG6xvwTaKCMwSU7hKxK6gt8mbsFIMaF5iDyjUg6iPnqc58higCr9fD4iTvWMziAmK2g73f/AADVWX0YXrlChirgOcqL3WXYBYpTfUuxzjkW30dI1C0ZW1RnjMopo4C56MIs6CgQrMER2cJoz9zjdO2iz17g2yZUjqzHWbuA4/ugiEz7DVRe/aLxmcvDQ5Cq+oWGWeDbAgiETXgArrVOFGzR0EkclxrVMcpfLgFThY5roe2yz95ZZkzcbj22+w2VG8Pz6Q/b5Gr6uM9mw04uo6ll4tOlhE8a8xNzGYihCJoT+u3I4kUIp6OM0X9CHHds8frbqsrXlh9CB62nj8L5a9Y4DHR/K68TgcHhoz607Qp34L72X0rdSdM+vAAAAAElFTkSuQmCC)](https://foundryvtt.com/releases/10.303)
[![FoundryVTT Version: v11.315](https://img.shields.io/badge/foundry-v11.315-brightgreen?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAAAXNSR0IArs4c6QAAAIRlWElmTU0AKgAAAAgABQESAAMAAAABAAEAAAEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIAAIdpAAQAAAABAAAAWgAAAAAAAABIAAAAAQAAAEgAAAABAAOgAQADAAAAAQABAACgAgAEAAAAAQAAAA6gAwAEAAAAAQAAAA4AAAAATspU+QAAAAlwSFlzAAALEwAACxMBAJqcGAAAAVlpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IlhNUCBDb3JlIDUuNC4wIj4KICAgPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICAgICAgPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIKICAgICAgICAgICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iPgogICAgICAgICA8dGlmZjpPcmllbnRhdGlvbj4xPC90aWZmOk9yaWVudGF0aW9uPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KTMInWQAAAiFJREFUKBVVks1rE1EUxc+d5tO0prZVSZsUhSBIPyC02ooWurJ0I7rQlRvdC/4N4h9gt7pyoRTswpWgILgQBIOIiC340VhbpC0Ek85MGmPmXc+baWpNGJg77/7uOffeB+z9FHB0FrH9eLwwqpOF0f34KrpsTicW+6L8KE8QhO/n8n1IOgtQHYZA+a/Ai9+Wd6v1g7liq5A2OjKSQNa9hkO4hAzOIylf6CHALk6hoWXsylPkfjyyApaJhVCxmERy5zLSuI7D8h1H5BWht1aBhS6wdI3pN7GabyuyS4JPrchzujmNjDxAVrrRL2PoxRSGxOfjssgEjkkJvVJBWu6h5M7YenvDoOO0OgicD4TPIKWbBG6xvwTaKCMwSU7hKxK6gt8mbsFIMaF5iDyjUg6iPnqc58higCr9fD4iTvWMziAmK2g73f/AADVWX0YXrlChirgOcqL3WXYBYpTfUuxzjkW30dI1C0ZW1RnjMopo4C56MIs6CgQrMER2cJoz9zjdO2iz17g2yZUjqzHWbuA4/ugiEz7DVRe/aLxmcvDQ5Cq+oWGWeDbAgiETXgArrVOFGzR0EkclxrVMcpfLgFThY5roe2yz95ZZkzcbj22+w2VG8Pz6Q/b5Gr6uM9mw04uo6ll4tOlhE8a8xNzGYihCJoT+u3I4kUIp6OM0X9CHHds8frbqsrXlh9CB62nj8L5a9Y4DHR/K68TgcHhoz607Qp34L72X0rdSdM+vAAAAAElFTkSuQmCC)](https://foundryvtt.com/releases/11.315)
[![FoundryVTT Version: v12.343](https://img.shields.io/badge/foundry-v12.343-brightgreen?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAAAXNSR0IArs4c6QAAAIRlWElmTU0AKgAAAAgABQESAAMAAAABAAEAAAEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIAAIdpAAQAAAABAAAAWgAAAAAAAABIAAAAAQAAAEgAAAABAAOgAQADAAAAAQABAACgAgAEAAAAAQAAAA6gAwAEAAAAAQAAAA4AAAAATspU+QAAAAlwSFlzAAALEwAACxMBAJqcGAAAAVlpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IlhNUCBDb3JlIDUuNC4wIj4KICAgPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICAgICAgPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIKICAgICAgICAgICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iPgogICAgICAgICA8dGlmZjpPcmllbnRhdGlvbj4xPC90aWZmOk9yaWVudGF0aW9uPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KTMInWQAAAiFJREFUKBVVks1rE1EUxc+d5tO0prZVSZsUhSBIPyC02ooWurJ0I7rQlRvdC/4N4h9gt7pyoRTswpWgILgQBIOIiC340VhbpC0Ek85MGmPmXc+baWpNGJg77/7uOffeB+z9FHB0FrH9eLwwqpOF0f34KrpsTicW+6L8KE8QhO/n8n1IOgtQHYZA+a/Ai9+Wd6v1g7liq5A2OjKSQNa9hkO4hAzOIylf6CHALk6hoWXsylPkfjyyApaJhVCxmERy5zLSuI7D8h1H5BWht1aBhS6wdI3pN7GabyuyS4JPrchzujmNjDxAVrrRL2PoxRSGxOfjssgEjkkJvVJBWu6h5M7YenvDoOO0OgicD4TPIKWbBG6xvwTaKCMwSU7hKxK6gt8mbsFIMaF5iDyjUg6iPnqc58higCr9fD4iTvWMziAmK2g73f/AADVWX0YXrlChirgOcqL3WXYBYpTfUuxzjkW30dI1C0ZW1RnjMopo4C56MIs6CgQrMER2cJoz9zjdO2iz17g2yZUjqzHWbuA4/ugiEz7DVRe/aLxmcvDQ5Cq+oWGWeDbAgiETXgArrVOFGzR0EkclxrVMcpfLgFThY5roe2yz95ZZkzcbj22+w2VG8Pz6Q/b5Gr6uM9mw04uo6ll4tOlhE8a8xNzGYihCJoT+u3I4kUIp6OM0X9CHHds8frbqsrXlh9CB62nj8L5a9Y4DHR/K68TgcHhoz607Qp34L72X0rdSdM+vAAAAAElFTkSuQmCC)](https://foundryvtt.com/releases/12.343)
[![FoundryVTT Version: v13.345](https://img.shields.io/badge/foundry-v13.345-brightgreen?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAAAXNSR0IArs4c6QAAAIRlWElmTU0AKgAAAAgABQESAAMAAAABAAEAAAEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIAAIdpAAQAAAABAAAAWgAAAAAAAABIAAAAAQAAAEgAAAABAAOgAQADAAAAAQABAACgAgAEAAAAAQAAAA6gAwAEAAAAAQAAAA4AAAAATspU+QAAAAlwSFlzAAALEwAACxMBAJqcGAAAAVlpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IlhNUCBDb3JlIDUuNC4wIj4KICAgPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICAgICAgPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIKICAgICAgICAgICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iPgogICAgICAgICA8dGlmZjpPcmllbnRhdGlvbj4xPC90aWZmOk9yaWVudGF0aW9uPgogICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KICAgPC9yZGY6UkRGPgo8L3g6eG1wbWV0YT4KTMInWQAAAiFJREFUKBVVks1rE1EUxc+d5tO0prZVSZsUhSBIPyC02ooWurJ0I7rQlRvdC/4N4h9gt7pyoRTswpWgILgQBIOIiC340VhbpC0Ek85MGmPmXc+baWpNGJg77/7uOffeB+z9FHB0FrH9eLwwqpOF0f34KrpsTicW+6L8KE8QhO/n8n1IOgtQHYZA+a/Ai9+Wd6v1g7liq5A2OjKSQNa9hkO4hAzOIylf6CHALk6hoWXsylPkfjyyApaJhVCxmERy5zLSuI7D8h1H5BWht1aBhS6wdI3pN7GabyuyS4JPrchzujmNjDxAVrrRL2PoxRSGxOfjssgEjkkJvVJBWu6h5M7YenvDoOO0OgicD4TPIKWbBG6xvwTaKCMwSU7hKxK6gt8mbsFIMaF5iDyjUg6iPnqc58higCr9fD4iTvWMziAmK2g73f/AADVWX0YXrlChirgOcqL3WXYBYpTfUuxzjkW30dI1C0ZW1RnjMopo4C56MIs6CgQrMER2cJoz9zjdO2iz17g2yZUjqzHWbuA4/ugiEz7DVRe/aLxmcvDQ5Cq+oWGWeDbAgiETXgArrVOFGzR0EkclxrVMcpfLgFThY5roe2yz95ZZkzcbj22+w2VG8Pz6Q/b5Gr6uM9mw04uo6ll4tOlhE8a8xNzGYihCJoT+u3I4kUIp6OM0X9CHHds8frbqsrXlh9CB62nj8L5a9Y4DHR/K68TgcHhoz607Qp34L72X0rdSdM+vAAAAAElFTkSuQmCC)](https://foundryvtt.com/releases/13.345)

[![Artifact Hub](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/foundry-vtt)](https://artifacthub.io/packages/search?repo=foundry-vtt)
[![GitHub Charts](https://github.com/hugoprudente/charts/workflows/Lint%20and%20Test%20Charts/badge.svg)](https://github.com/hugoprudente/charts/actions/)
[![Patreon](https://img.shields.io/badge/patreon-donate-yellow.svg)](https://patreon.com/nerdweekoficial)
[![GitHub license](https://img.shields.io/github/license/hugoprudente/charts)](https://github.com/hugoprudente/charts/blob/master/LICENSE)
[![GitHub forks](https://img.shields.io/github/forks/hugoprudente/charts)](https://github.com/hugoprudente/charts/network)
[![GitHub stars](https://img.shields.io/github/stars/hugoprudente/charts)](https://github.com/hugoprudente/charts/stargazers)

[Foundry VTT](http://foundryvtt.com/) is a standalone application built for experiencing multiplayer tabletop RPGs using a feature-rich and modern self-hosted application where your players connect directly through the browser.

## Introduction

You can get a [FoundryVTT](https://foundryvtt.com) instance up and running in
minutes using this chart and Felddy [foundryvtt-docker](https://github.com/felddy/foundryvtt-docker) Docker container.

## Prerequisites

- 512 MB of RAM
- Kubernetes 1.19+
- PV provisioner support in the underlying infrastructure

## Installing the Chart

To install the chart with the release name `my-release`, run:

```bash
helm install my-release ./incubator/foundry-vtt
```

or

```bash
$ helm install my-release \
    --set foundryvtt.adminPassword='MyPa$$word' \
    --set foundryvtt.username='my-foundry-website-user' \
    --set foundryvtt.password='my-foundry-website-user-pass' \
    ./incubator/foundry-vtt
```

> **NOTE**: Check the [Values configurations](#required-combinations) for the combinations on how to fetch Foundry VTT application using Felddy's [foundryvtt-docker](https://github.com/felddy/foundryvtt-docker) as an alternative to built your own container.

or

```bash
helm install my-release ./incubator/foundry-vtt -f incubator/foundry-vtt/values.yaml
```

This command deploys a Foundry VTT dedicated server with sensible defaults.

> **Tip**: List all releases using `helm list`

## Uninstalling the Chart

To uninstall/delete the `my-release` deployment:

```bash
helm uninstall my-release
```

The command removes all the Kubernetes components associated with the chart and deletes the release.

## Configuration

Refer to [values.yaml](values.yaml) for the full run-down on defaults. These are a mixture of Kubernetes and Foundry VTT-related directives that map to environment variables in the [Foundry VTT](https://github.com/felddy/foundryvtt-docker) Docker image by Felddy.

Specify each parameter using the `--set key=value[,key=value]` argument to `helm install`. For example,

```bash
$ helm install my-release \
    --set foundryvtt.adminPassword='MyPa$$word' \
    ./incubator/foundry-vtt
```

Alternatively, a YAML file that specifies the values for the parameters can be provided while installing the chart. For example,

```bash
helm install my-release -f values.yaml ./incubator/foundry-vtt
```

> **Tip**: You can use the default [values.yaml](values.yaml)

## Values Configurations

### Required combinations

One of the three combinations of environment variables listed below must be set
in order for the container to locate and install a Foundry Virtual Tabletop
distribution. Although all variables may be specified together, they are
evaluated in the following order of precedence:

1. `foundryvtt.releaseUrl`, _or_
1. `foundryvtt.username` and `foundryvtt.password`, _or_
1. `container.cache`

#### Credentials variables

| Name                | Purpose                                                                                                     |
| ------------------- | ----------------------------------------------------------------------------------------------------------- |
| foundryvtt.password | Account password for foundryvtt.com. Required for downloading an application distribution.                  |
| foundryvtt.username | Account username or email address for foundryvtt.com. Required for downloading an application distribution. |

#### Pre-signed URL variable

| Name                   | Purpose                                                                                                   |
| ---------------------- | --------------------------------------------------------------------------------------------------------- |
| foundryvtt.releaseUrl | S3 pre-signed URL generate from the user's profile. Required for downloading an application distribution. |

#### Pre-cached distribution variable

A distribution can be downloaded and placed into a cache directory. The
distribution's name must be of the form: `foundryvtt-0.7.10.zip`

> Before Felddy's v9.255.1 and v10.260.1 container you Must set this paramenter,
> after those versions the `/data/container_cache` is created by default and
> used.

| Name                | Purpose                                                                                                                                                                                                                                             |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| container.cache     | Optional: Set a different path to cache downloads of the Foundry distribution archive and speed up subsequent container startups. By default Felddy's container create the `/data/container_cache` if no value is specified                         |
| container.cacheSize | Set the maximum number of distribution versions to keep in the cache. The minimum is `1`. When the limit is exceeded, the oldest versions (lowest version numbers) are removed first. Unset to disable cache size management and keep all versions. |

### Optional for Container

| Parameter                | Description                                                                                                                                                                                                                                                                                                                                                                                                                  | Default   |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| container.gid            | `gid` the deamon will be run under.                                                                                                                                                                                                                                                                                                                                                                                          | `foundry` |
| container.patches        | Set a path to a directory of shell scripts to be sourced after Foundry is installed but before it is started. The path should be in `/data` or another persistent mount point in the container. e.g.; `/data/patches` Patch files are sourced in lexicographic order. `container.patches` are processed after `container.patch_urls`.                                                                                        |           |
| container.patchUrls      | Set to a list of URLs to be sourced after Foundry is installed but before it is started. Patch URLs are sourced in the order specified. `container.patch_urls` are processed before `container.patches`. ⚠️ **Only use patch URLs from trusted sources!**                                                                                                                                                                    |           |
| container.preserveConfig | Normally new `options.json` and `admin.txt` files are generated by the container at each startup. Setting this to `true` prevents the container from modifying these files when they exist. If they do not exist, they will be created as normal.                                                                                                                                                                            | `false`   |
| container.preserveOwner  | Normally the ownership of the `/data` directory and its contents are changed to match that of the server at startup. Setting this to a regular expression will exclude any matching paths and preserve their ownership. _Note: This is a match on the whole path, not a search._ This is useful if you want mount a volume as read-only inside `/data` (e.g.; a volume that contains assets mounted at `/data/Data/assets`). |           |
| container.timezone       | Container [TZ database name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List)                                                                                                                                                                                                                                                                                                                              | `UTC`     |
| container.uid            | `uid` the daemon will be run under.                                                                                                                                                                                                                                                                                                                                                                                          | `foundry` |
| container.verbose        | Set to `true` to enable verbose logging for the container utility scripts.                                                                                                                                                                                                                                                                                                                                                   | false     |

---

### Optional for Foundry VTT

| Parameter                    | Description                                                                                                                                                                                                                                                                                                                             | Default            |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| foundryvtt.adminPassword     | Admin password to be applied at startup. If omitted the admin password will be cleared.                                                                                                                                                                                                                                                 | admin              |
| foundryvtt.cssTheme         | Choose the CSS theme for the setup page. Choose from `foundry`, `fantasy`, or `scifi`.                                                                                                                                                                                                                                                  | foundry            |
| foundryvtt.hostname          | A custom hostname to use in place of the host machine's public IP address when displaying the address of the game session. This allows for reverse proxies or DNS servers to modify the public address.                                                                                                                                 | foundry.domain.com |
| foundryvtt.language          | The default application language and module which provides the core translation files.                                                                                                                                                                                                                                                  | `en.core`          |
| foundryvtt.license_key       | The license key to install. e.g.; AAAA-BBBB-CCCC-DDDD-EEEE-FFFF If left unset, a license key will be fetched when using account authentication. If multiple license keys are associated with an account, one will be chosen at random. Specific licenses can be selected by passing in an integer index. The first license key being 1. |
| foundryvtt.minifyStaticFiles | Set to `true` to reduce network traffic by serving minified static JavaScript and CSS files. Enabling this setting is recommended for most users, but module developers may wish to disable it                                                                                                                                          | true               |
| foundryvtt.proxyPort         | Inform the Foundry Server that the software is running behind a reverse proxy on some other port. This allows the invitation links created to the game to include the correct external port.                                                                                                                                            | 80                 |
| foundryvtt.proxySSL          | Indicates whether the software is running behind a reverse proxy that uses SSL. This allows invitation links and A/V functionality to work as if the Foundry Server had SSL configured directly.                                                                                                                                        | true               |
| foundryvtt.routePrefix       | A string path which is appended to the base hostname to serve Foundry VTT content from a specific namespace. For example setting this to `demo` will result in data being served from `http://x.x.x.x:30000/demo/`.                                                                                                                     | null               |
| foundryvtt.s3.awsConfig      | configure the data in the values.yaml to generate the [awsConfig.json](https://foundryvtt.com/article/aws-s3/) or `true` for AWS environment variable [credentials evaluation](https://docs.aws.amazon.com/sdk-for-javascript/v2/developer-guide/setting-credentials-node.html) usage                                                   | false              |
| foundryvtt.sslCert           | An absolute or relative path that points towards a SSL certificate file which is used jointly with the sslKey option to enable SSL and https connections. If both options are provided, the server will start using HTTPS automatically.                                                                                                | null               |
| foundryvtt.sslKey            | An absolute or relative path that points towards a SSL key file which is used jointly with the sslCert option to enable SSL and https connections. If both options are provided, the server will start using HTTPS automatically.                                                                                                       | null               |
| foundryvtt.turnConfigs       | An array of TURN configurations in JSON format. See: [Using a Custom Relay Server](https://foundryvtt.com/article/audio-video/#custom). To disable the internal relay server comment the paramenter.                                                                                                                                    |                    |
| foundryvtt.turnMaxPort       | Sets the maximum UDP port used by the internal [TURN relay server](https://foundryvtt.com/article/audio-video/). This value must be greater than `49152`. _Note: To use the internal relay server its ports must be published._                                                                                                         |                    |
| foundryvtt.upnp              | Allow Universal Plug and Play to automatically request port forwarding for the Foundry VTT port to your local network address.                                                                                                                                                                                                          | false              |
| foundryvtt.version           | Version of Foundry Virtual Tabletop to install.                                                                                                                                                                                                                                                                                         | 0.7.10             |
| foundryvtt.world             | The world startup at system start.                                                                                                                                                                                                                                                                                                      | null               |

## Persistence

The [Foundry VTT Docker](https://github.com/felddy/foundryvtt-docker) image can be built and published to a private registry. You can use that to store a default state like worlds, modules, assets and extras in the /data.

By default a PersistentVolumeClaim is created and mounted for saves but not mods. In order to disable this functionality

you can change the values.yaml to disable persistence under the sub-sections under `persistence`.

> _"An emptyDir volume is first created when a Pod is assigned to a Node, and exists as long as that Pod is running on that node. When a Pod is removed from a node for any reason, the data in the emptyDir is deleted forever."_

## TLS ingress-controller and Cert Manager

You can use either **ingress-nginx** or **contour** as the ingress controller of this helm, to setup.

### Setting up `ingress-nginx`

If you decide to use _contour_, go to the next step

```
kubectl create ns ingress-nginx
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/master/deploy/static/provider/cloud/deploy.yaml
```

### Setting up `projectcontour`

If you choose _ingress-nginx_, go to the next step

```
kubectl create ns projectcontour
kubectl apply -f https://projectcontour.io/quickstart/contour.yaml
```

### Create the namespace for cert-manager

```
kubectl create namespace cert-manager
```

### Add the Jetstack Helm repository

```
helm repo add jetstack https://charts.jetstack.io
```

### Update your local Helm chart repository cache

```
helm repo update
```

### Install the cert-manager Helm chart

> **Important:**
> If you are running Kubernetes v1.15 or below, you will need to add the `--validate=false flag to your kubectl apply command above else you will receive a validation error relating to the x-kubernetes-preserve-unknown-fields field in cert-manager’s CustomResourceDefinition resources. This is a benign error and occurs due to the way kubectl performs resource validation. Reference official [documentation](https://cert-manager.io/docs/installation/kubernetes/)

```
helm install \
  cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --version v1.0.3 \
  --set installCRDs=true
```

```
kubectl get pods --namespace cert-manager
NAME                                       READY   STATUS    RESTARTS   AGE
cert-manager-5c6866597-zw7kh               1/1     Running   0          2m
cert-manager-cainjector-577f6d9fd7-tr77l   1/1     Running   0          2m
cert-manager-webhook-787858fcdb-nlzsq      1/1     Running   0          2m
```

### Checking emited certificate

```
kubectl get certificates
NAME                      READY   SECRET                    AGE
tls-foundry-vtt-ingress   True    tls-foundry-vtt-ingress   34m
```

```
kubectl describe certificate tls-foundry-vtt-ingress
Events:
  Type    Reason        Age   From          Message
  ----    ------        ----  ----          -------
  Normal  GeneratedKey  35m   cert-manager  Generated a new private key
  Normal  Requested     35m   cert-manager  Created new CertificateRequest resource "tls-foundry-vtt-ingress-1297638063"
  Normal  Issued        22m   cert-manager  Certificate issued successfully
```

## Backup & Backup Restauration

Identifying the pod

```bash
kubectl get pods --namespace foundry-vtt
NAME                                   READY   STATUS    RESTARTS   AGE
foundry-vtt-5b5864c7bc-v6r7d           1/1     Running   0          5d5h
```

Generating the backup on the /tmp/ directory.

```bash
kubectl exec -it foundry-vtt-5b5864c7bc-v6r7d -- /bin/sh -c "cd /data && tar -cvzf /data/backup.tar.gz Data"
```

Output:

```log
Data/
Data/worlds/
Data/worlds/README.txt
Data/worlds/waterdeep/
Data/worlds/waterdeep/world.json
Data/worlds/waterdeep/scenes/
Data/worlds/waterdeep/
Data/worlds/the-masters-vault/
...
Data/assets/characters/tiefling_bard.png
Data/assets/handout/
Data/assets/handout/ellaria_will.png
Data/assets/handout/ellarias_memory.jpg
Data/assets/tiles/
Data/assets/tiles/alcaeus_home.png
Data/assets/tiles/helenes_grave.png
Data/assets/tiles/vixthras_lair.png
```

Downloading the backup!

```bash
kubectl cp foundry-vtt-5b5864c7bc-v6r7d:/data/backup.tar.gz backup.tar.gz
backup.tar.gz
```

Resauring a Backup!

```bash
kubectl cp backup.tar.gz nerdweek-foundry-vtt-ddc84f8b5-dkz4c:/data/backup.tar.gz
kubectl exec -it  nerdweek-foundry-vtt-ddc84f8b5-dkz4c -- /bin/sh -c "cd /data/ && tar -xvzf backup.tar.gz && rm -v /data/backup.tar.gz"
```

Output:

```log
Data/
Data/worlds/
Data/worlds/README.txt
Data/worlds/waterdeep/
...
Data/assets/handout/ellarias_memory.jpg
Data/assets/tiles/
Data/assets/tiles/alcaeus_home.png
Data/assets/tiles/helenes_grave.png
Data/assets/tiles/vixthras_lair.png
removed '/data/backup.tar.gz'
```

from typing import Optional


DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = {"en", "pt"}


TRANSLATIONS = {
    "en": {
        "page_title": "PBI Relations Extractor",
        "app_title": "Power BI model relationships extractor",
        "app_description": (
            "Upload a <code>.pbit</code> file to extract relationships between tables. "
            "The same extraction is also available at the "
            "<code>POST /api/extract-relations</code> endpoint."
        ),
        "language_label": "Language",
        "language_pt": "🇧🇷 Portuguese",
        "language_en": "🇺🇸 English",
        "choose_file": "Choose file",
        "no_file_chosen": "No file chosen",
        "submit_button": "Upload and extract",
        "error_label": "Error:",
        "result_title": "Result",
        "file_label": "File:",
        "relationship_total_label": "Total relationships:",
        "tables_label": "Tables:",
        "measures_label": "Measures:",
        "pages_label": "Pages:",
        "visuals_label": "Visuals:",
        "relationship_diagram_title": "Relationship diagram",
        "zoom_in": "Zoom +",
        "zoom_out": "Zoom -",
        "fit_view": "Fit to view",
        "reset_view": "Reset view",
        "export_png": "Export PNG",
        "fullscreen": "Full screen",
        "exit_fullscreen": "Exit full screen",
        "export_failed": "Could not export the diagram as PNG.",
        "diagram_hint": "Tip: use scroll to zoom and drag the background or nodes to navigate.",
        "table_filter_title": "Filter tables",
        "table_filter_toggle": "Table selection",
        "role_panel_toggle": "Table roles",
        "fact_prefixes_label": "Fact prefixes",
        "dim_prefixes_label": "Dimension prefixes",
        "reset_prefixes": "Reset prefixes",
        "role_auto": "Auto",
        "role_fact": "Fact",
        "role_dimension": "Dimension",
        "role_snowflake": "Snowflake",
        "role_other": "Other",
        "table_filter_placeholder": "Search tables",
        "toggle_local_date_tables": "Show LocalDate Table tables",
        "clear_filter": "Clear filter",
        "filter_empty": "No tables found",
        "filter_selected_none": "All tables visible",
        "filter_selected_count": "{count} selected",
        "view_all_tables": "All tables",
        "view_current_selection": "Current selection",
        "view_save_current": "Save current view",
        "view_save_disabled": "Select one or more tables to save a custom view",
        "view_new_prompt": "Name for the new view:",
        "view_new_default": "Custom view",
        "view_remove": "Remove view",
        "relationship_details_title": "Relationship details",
        "relationship_details_empty": "Select a relationship to inspect it here.",
        "relationship_from_label": "From",
        "relationship_to_label": "To",
        "relationship_columns_label": "Columns",
        "relationship_cardinality_label": "Cardinality",
        "relationship_filter_label": "Filter",
        "relationships_table_title": "Relationships table",
        "from_column": "from",
        "to_column": "to",
        "from_field_column": "from column",
        "to_field_column": "to column",
        "cardinality_column": "cardinality",
        "filter_direction_column": "filter direction",
        "measures_definitions_title": "Measures and definitions",
        "table_column": "Table",
        "measure_column": "Measure",
        "definition_column": "Definition (DAX)",
        "no_measures_found": "No measures found in the model.",
        "pages_visuals_title": "Pages and visuals",
        "page_column": "Page",
        "visual_count_column": "Visual count",
        "visual_types_column": "Visual types",
        "potentially_unused_title": "Potentially unused items",
        "unused_summary": "Tables: {table_count}, Measures: {measure_count}, Columns: {column_count}",
        "unused_tables_label": "Tables with no detected usage:",
        "no_relationships_to_render": "No relationships to render.",
        "diagram_aria_label": "Relationship diagram",
        "upload_missing_error": "No .pbit file was sent.",
        "invalid_format_error": "Invalid format. Please upload a .pbit file.",
        "invalid_format_ui_error": "Invalid format. Please select a .pbit file.",
        "extract_failed_error": "Failed to extract relationships: {error}",
        "process_failed_error": "Could not process the file: {error}",
    },
    "pt": {
        "page_title": "Extrator de Relações PBI",
        "app_title": "Extrator de relacionamentos de modelo Power BI",
        "app_description": (
            "Faça upload de um arquivo <code>.pbit</code> para extrair as relações entre tabelas. "
            "Esta mesma extração também está disponível no endpoint "
            "<code>POST /api/extract-relations</code>."
        ),
        "language_label": "Idioma",
        "language_pt": "🇧🇷 Português",
        "language_en": "🇺🇸 Inglês",
        "choose_file": "Escolher arquivo",
        "no_file_chosen": "Nenhum arquivo selecionado",
        "submit_button": "Enviar e extrair",
        "error_label": "Erro:",
        "result_title": "Resultado",
        "file_label": "Arquivo:",
        "relationship_total_label": "Total de relacionamentos:",
        "tables_label": "Tabelas:",
        "measures_label": "Medidas:",
        "pages_label": "Páginas:",
        "visuals_label": "Visuais:",
        "relationship_diagram_title": "Diagrama de relacionamento",
        "zoom_in": "Zoom +",
        "zoom_out": "Zoom -",
        "fit_view": "Auto enquadrar",
        "reset_view": "Resetar visão",
        "export_png": "Exportar PNG",
        "fullscreen": "Tela cheia",
        "exit_fullscreen": "Sair da tela cheia",
        "export_failed": "Não foi possível exportar o diagrama em PNG.",
        "diagram_hint": "Dica: use o scroll para zoom e arraste o fundo ou os nós para navegar.",
        "table_filter_title": "Filtrar tabelas",
        "table_filter_toggle": "Selecao de tabelas",
        "role_panel_toggle": "Tipos de tabela",
        "fact_prefixes_label": "Prefixos de fato",
        "dim_prefixes_label": "Prefixos de dimensao",
        "reset_prefixes": "Resetar prefixos",
        "role_auto": "Auto",
        "role_fact": "Fato",
        "role_dimension": "Dimensao",
        "role_snowflake": "Snowflake",
        "role_other": "Outro",
        "table_filter_placeholder": "Buscar tabelas",
        "toggle_local_date_tables": "Mostrar tabelas LocalDate Table",
        "clear_filter": "Limpar filtro",
        "filter_empty": "Nenhuma tabela encontrada",
        "filter_selected_none": "Todas as tabelas visiveis",
        "filter_selected_count": "{count} selecionadas",
        "view_all_tables": "Todas as tabelas",
        "view_current_selection": "Selecao atual",
        "view_save_current": "Salvar visualizacao atual",
        "view_save_disabled": "Selecione uma ou mais tabelas para salvar uma visualizacao personalizada",
        "view_new_prompt": "Nome da nova visualizacao:",
        "view_new_default": "Visualizacao personalizada",
        "view_remove": "Remover visualizacao",
        "relationship_details_title": "Detalhes do relacionamento",
        "relationship_details_empty": "Selecione um relacionamento para ver os detalhes aqui.",
        "relationship_from_label": "Origem",
        "relationship_to_label": "Destino",
        "relationship_columns_label": "Colunas",
        "relationship_cardinality_label": "Cardinalidade",
        "relationship_filter_label": "Filtro",
        "relationships_table_title": "Tabela de relações",
        "from_column": "from",
        "to_column": "to",
        "from_field_column": "coluna origem",
        "to_field_column": "coluna destino",
        "cardinality_column": "cardinalidade",
        "filter_direction_column": "direção do filtro",
        "measures_definitions_title": "Medidas e definições",
        "table_column": "Tabela",
        "measure_column": "Medida",
        "definition_column": "Definição (DAX)",
        "no_measures_found": "Nenhuma medida encontrada no modelo.",
        "pages_visuals_title": "Páginas e visuais",
        "page_column": "Página",
        "visual_count_column": "Quantidade de visuais",
        "visual_types_column": "Tipos de visual",
        "potentially_unused_title": "Itens potencialmente não utilizados",
        "unused_summary": "Tabelas: {table_count}, Medidas: {measure_count}, Colunas: {column_count}",
        "unused_tables_label": "Tabelas sem uso detectado:",
        "no_relationships_to_render": "Nenhum relacionamento para renderizar.",
        "diagram_aria_label": "Diagrama de relacionamentos",
        "upload_missing_error": "Arquivo .pbit não enviado.",
        "invalid_format_error": "Formato inválido. Envie um arquivo .pbit.",
        "invalid_format_ui_error": "Formato inválido. Selecione um arquivo .pbit.",
        "extract_failed_error": "Falha ao extrair relacionamentos: {error}",
        "process_failed_error": "Não foi possível processar o arquivo: {error}",
    },
}


def get_locale_from_header(accept_language: Optional[str]) -> str:
    if not accept_language:
        return DEFAULT_LOCALE

    for language in accept_language.split(","):
        code = language.split(";")[0].strip().lower()
        if not code:
            continue
        base_code = code.split("-")[0]
        if base_code in SUPPORTED_LOCALES:
            return base_code

    return DEFAULT_LOCALE


def normalize_locale(locale: Optional[str]) -> str:
    if not locale:
        return DEFAULT_LOCALE

    normalized = locale.strip().lower().split("-")[0]
    if normalized in SUPPORTED_LOCALES:
        return normalized
    return DEFAULT_LOCALE


def get_translations(locale: str) -> dict[str, str]:
    return TRANSLATIONS.get(locale, TRANSLATIONS[DEFAULT_LOCALE])

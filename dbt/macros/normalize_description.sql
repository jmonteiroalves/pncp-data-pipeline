{% macro normalize_description(column) -%}
    lower(
        trim(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            regexp_replace(
                                {{ column }},
                                r'^\s*\[[^\]]{1,80}\]\s*[-–—]\s*',
                                ''
                            ),
                            r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b',
                            '[CPF]'
                        ),
                        r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b',
                        '[EMAIL]'
                    ),
                    r'\b\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b',
                    '[TELEFONE]'
                ),
                r'\s+',
                ' '
            )
        )
    )
{%- endmacro %}

{#- Render a list var as a SQL IN-list: ('a', 'b'). -#}
{% macro status_list(var_name) -%}
    ({% for s in var(var_name) %}'{{ s }}'{% if not loop.last %}, {% endif %}{% endfor %})
{%- endmacro %}

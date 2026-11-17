select *
from unnest([
    struct('Tecnologia' as categoria, 'Hardware, software, telecomunicações e serviços de TI.' as descricao),
    struct('Saúde' as categoria, 'Medicamentos, materiais, equipamentos e serviços de saúde.'),
    struct('Transporte' as categoria, 'Veículos, peças, combustíveis, fretes e logística.'),
    struct('Serviços gerais' as categoria, 'Limpeza, vigilância, manutenção, facilities e apoio administrativo.'),
    struct('Alimentação' as categoria, 'Gêneros alimentícios, refeições e catering.'),
    struct('Infraestrutura' as categoria, 'Obras, engenharia, saneamento e construção.'),
    struct('Outros' as categoria, 'Itens sem encaixe seguro nas demais categorias.'),
    struct('Não classificado' as categoria, 'Descrição ainda não enriquecida pela IA.')
])

import streamlit as st
import pandas as pd
import mysql.connector
import plotly.express as px

# Function to fetch data using st.connection
@st.cache_data(ttl=600)
def get_data():
    conn = st.connection('mysql', type='sql')

    # Fetch all necessary data in fewer queries
    df_unidade = conn.query("SELECT id_unidade, sigla, id_unidade_fk FROM Unidade", ttl=600)
    
    query = """
    SELECT 
        m.id_militar, 
        m.nome, 
        m.id_posto_graduacao_fk, 
        m.id_quadro_fk, 
        m.id_unidade_atual_fk,
        pg.id_posto_graduacao,
        pg.sigla AS posto_graduacao_sigla,
        pg.descricao AS posto_graduacao,
        q.id_quadro,
        q.sigla AS quadro_sigla,
        q.descricao AS quadro
    FROM Militar m
    JOIN Posto_Graduacao pg ON m.id_posto_graduacao_fk = pg.id_posto_graduacao
    JOIN Quadro q ON m.id_quadro_fk = q.id_quadro
    """
    df = conn.query(query, ttl=600)

    df_especialidades_query = """
    SELECT 
        me.id_militar_fk,
        GROUP_CONCAT(e.tipo_especialidade SEPARATOR ', ') AS especialidades
    FROM militar_especialidade me
    JOIN Especialidade e ON me.id_especialidade_fk = e.id_especialidade
    GROUP BY me.id_militar_fk
    """
    df_especialidades = conn.query(df_especialidades_query, ttl=600)

    # Optimized path building
    unit_map = df_unidade.set_index('id_unidade').to_dict('index')
    
    @st.cache_data
    def get_unit_path_optimized(unit_id, unit_map):
        path = []
        current_id = unit_id
        while pd.notna(current_id):
            unit_info = unit_map.get(current_id)
            if unit_info:
                path.append(unit_info['sigla'])
                current_id = unit_info.get('id_unidade_fk')
            else:
                break
        return ' / '.join(reversed(path))

    df['unidade'] = df['id_unidade_atual_fk'].apply(lambda x: get_unit_path_optimized(x, unit_map))

    # Merge especialidades
    df = pd.merge(df, df_especialidades, left_on='id_militar', right_on='id_militar_fk', how='left')
    df['especialidades'] = df['especialidades'].fillna('Nenhuma')

    # Clean up columns
    df = df[['nome', 'posto_graduacao_sigla', 'posto_graduacao', 'id_posto_graduacao', 'quadro_sigla', 'quadro', 'unidade', 'id_unidade_atual_fk', 'especialidades']]
    df = df.rename(columns={'id_unidade_atual_fk': 'id_unidade'})
    df = df.sort_values(by='id_posto_graduacao').reset_index(drop=True)

    return df

# Main app
def main():
    st.set_page_config(layout="wide")
    st.title("🚒 Visualização de Dados do CBMMA | COCBN")

    df = get_data()

    # Sidebar
    st.sidebar.header("Filtros")
    
    # Get unique unidade paths and their corresponding IDs, then sort by ID
    unidades_sorted_df = df[['unidade', 'id_unidade']].drop_duplicates()
    unidades_cocbn = unidades_sorted_df[unidades_sorted_df['unidade'].str.startswith('COCB-N', na=False)]
    unidades_cocbn_sorted = unidades_cocbn.sort_values(by='id_unidade')
    unidades_options = unidades_cocbn_sorted['unidade'].tolist()

    # Get unique posto_graduacao_sigla and their corresponding IDs, then sort by ID
    postos_sorted_df = df[['posto_graduacao_sigla', 'id_posto_graduacao']].drop_duplicates().sort_values(by='id_posto_graduacao')
    postos_options = postos_sorted_df['posto_graduacao_sigla'].tolist()
    
    quadros_options = sorted(df['quadro_sigla'].unique())

    unidades = st.sidebar.multiselect(
        "Selecione a Unidade", 
        options=unidades_options, 
        default=unidades_options,
        format_func=lambda path: path.split(' / ')[-1]
    )
    postos = st.sidebar.multiselect("Selecione o Posto/Graduação", options=postos_options, default=postos_options)
    quadros = st.sidebar.multiselect("Selecione o Quadro", options=quadros_options, default=quadros_options)

    # Add especialidades filter
    all_especialidades = df['especialidades'].str.split(', ').explode().unique()
    especialidades_options = sorted([spec for spec in all_especialidades if spec != 'Nenhuma'])
    especialidades = st.sidebar.multiselect("Selecione a Especialidade", options=especialidades_options)

    # Filter dataframe based on selected units, posts, and quadro
    df_selection = df.query(
        "unidade == @unidades and posto_graduacao_sigla == @postos and quadro_sigla == @quadros"
    )

    # Apply especialidades filter
    if especialidades:
        # Create a boolean mask to filter rows based on selected specialties
        # A row is selected if its 'especialidades' string contains any of the selected specialties
        # Handle potential NaN values by converting to string first
        mask_especialidades = df_selection['especialidades'].astype(str).apply(
            lambda x: any(esp.strip() in (s.strip() for s in x.split(',')) for esp in especialidades)
        )
        df_selection = df_selection[mask_especialidades]

    # --- KPIs ---
    total_militares = df_selection.shape[0]
    total_unidades = len(df_selection['unidade'].unique())
    total_postos = len(df_selection['posto_graduacao_sigla'].unique())

    left_column, middle_column, right_column = st.columns(3)
    with left_column:
        st.metric(label="Total de Militares", value=total_militares)
    with middle_column:
        st.metric(label="Unidades Selecionadas", value=total_unidades)
    with right_column:
        st.metric(label="Postos/Grad. Selecionados", value=total_postos)

    st.markdown("---")

    # Main page
    st.header("Distribuição de Militares por Unidade")
    # Create a temporary column for display
    df_selection['unidade_sigla_display'] = df_selection['unidade'].apply(lambda x: x.split(' / ')[-1])

    unidade_counts = df_selection['unidade_sigla_display'].value_counts().reset_index()
    unidade_counts.columns = ['Unidade', 'Quantidade']
    fig3 = px.bar(
        unidade_counts, 
        x='Unidade', # Use the new display column
        y='Quantidade', 
        title="Militares por Unidade",
        template="plotly_white"
    )
    st.plotly_chart(fig3)

    st.header("Distribuição de Militares por Quadro")
    quadro_counts = df_selection['quadro_sigla'].value_counts().reset_index()
    quadro_counts.columns = ['Quadro', 'Quantidade']
    fig2 = px.pie(
        quadro_counts, 
        values='Quantidade', 
        names='Quadro', 
        title="Distribuição por Quadro",
        template="plotly_white"
    )
    st.plotly_chart(fig2)

    st.header("Distribuição de Militares por Posto/Graduação")
    posto_graduacao_counts = df_selection['posto_graduacao_sigla'].value_counts().reset_index()
    posto_graduacao_counts.columns = ['Posto/Graduação', 'Quantidade']
    fig1 = px.bar(
        posto_graduacao_counts, 
        x='Posto/Graduação', 
        y='Quantidade', 
        title="Militares por Posto/Graduação",
        template="plotly_white"
    )
    st.plotly_chart(fig1)
    
   # st.header("Dados dos Militares")
   # st.dataframe(df_selection.sort_values(by='id_posto_graduacao').drop('id_posto_graduacao', axis=1))

if __name__ == "__main__":
    main()

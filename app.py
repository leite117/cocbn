
import streamlit as st
import pandas as pd
import mysql.connector
import plotly.express as px

# Function to fetch data using st.connection
@st.cache_data
def get_data():
    conn = st.connection('mysql', type='sql')
    query = """
    SELECT
        m.nome,
        pg.sigla AS posto_graduacao_sigla,
        pg.descricao AS posto_graduacao,
        q.sigla AS quadro_sigla,
        q.descricao AS quadro,
        u.sigla AS unidade,
        GROUP_CONCAT(e.tipo_especialidade SEPARATOR ', ') AS especialidades
    FROM Militar m
    JOIN Posto_Graduacao pg ON m.id_posto_graduacao_fk = pg.id_posto_graduacao
    JOIN Quadro q ON m.id_quadro_fk = q.id_quadro
    JOIN Unidade u ON m.id_unidade_atual_fk = u.id_unidade
    LEFT JOIN militar_especialidade me ON m.id_militar = me.id_militar_fk
    LEFT JOIN Especialidade e ON me.id_especialidade_fk = e.id_especialidade
    GROUP BY m.id_militar, m.nome, pg.sigla, pg.descricao, q.sigla, q.descricao, u.sigla
    ORDER BY pg.id_posto_graduacao
    """
    df = conn.query(query, ttl=600) # Cache data for 10 minutes
    df['especialidades'] = df['especialidades'].fillna('Nenhuma')
    return df

# Main app
def main():
    st.set_page_config(layout="wide")
    st.title("🚒 Visualização de Dados do CBMMA | COCBN")

    df = get_data()

    # Sidebar
    st.sidebar.header("Filtros")
    
    # Obtenha valores únicos e ordene-os para melhor usabilidade
    unidades_options = sorted(df['unidade'].unique())
    postos_options = sorted(df['posto_graduacao_sigla'].unique())
    quadros_options = sorted(df['quadro_sigla'].unique())

    unidades = st.sidebar.multiselect("Selecione a Unidade", options=unidades_options, default=unidades_options)
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
    unidade_counts = df_selection['unidade'].value_counts().reset_index()
    unidade_counts.columns = ['Unidade', 'Quantidade']
    fig3 = px.bar(
        unidade_counts, 
        x='Unidade', 
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
    
    st.header("Dados dos Militares")
    st.dataframe(df_selection)

if __name__ == "__main__":
    main()

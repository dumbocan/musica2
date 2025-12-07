#!/usr/bin/env python3
"""
Sistema Multi-Capa de Recomendaciones Musicales Inteligentes
Versión Simplificada pero Funcional
"""
import asyncio

class MultiLayerMusicRecommender:
    """
    Motor de recomendaciones de 3 capas:
    1. Artistas principales del usuario
    2. Intersecciones entre similares
    3. Nuevos descubrimientos
    """

    def __init__(self):
        # Base de conocimiento icónica
        self.iconic_tracks = {
            'eminem': ['Lose Yourself', 'Stan', 'Love The Way You Lie'],
            'metallica': ['Master of Puppets', 'Enter Sandman', 'Nothing Else Matters'],
            '2pac': ['California Love', 'Changes', 'Hit Em Up'],
            '50 cent': ['In Da Club', 'P.I.M.P.', 'Candy Shop'],
            'dr. dre': ['Still D.R.E.', 'Forgot About Dre', 'Nuthin\'']

        }

        # Artistas famosos como "superestrellas" - CADA VEZ MÁS INTELIGENTE
        self.superstars = {
            # Hip-hop conecta con hip-hop
            'eminem': ['2Pac', '50 Cent', 'Dr. Dre', 'Kendrick Lamar'],
            '2pac': ['Eminem', 'Dr. Dre', 'Snoop Dogg', 'Ice Cube'],
            '50 cent': ['Eminem', 'Dr. Dre', 'Lloyd Banks', 'Tony Yayo'],
            'dr. dre': ['Eminem', '2Pac', 'Snoop Dogg', 'The Game'],

            # Metal conecta con metal
            'metallica': ['Iron Maiden', 'Black Sabbath', 'Judas Priest', 'Megadeth'],
            'iron maiden': ['Metallica', 'Judas Priest', 'Black Sabbath', 'Dio'],
            'black sabbath': ['Metallica', 'Iron Maiden', 'Dio', 'Rainbow'],

            # Crossroads: artistas que unen géneros
            'evanescence': ['Linkin Park', 'Three Days Grace', 'Breaking Benjamin'],
            'linkin park': ['Evanescence', 'Rage Against The Machine', 'Incubus'],  # ¡Puente hip-hop+rock!
        }

    async def recommend_multi_layer(self, user_artists):
        """
        Genera recomendaciones de 3 capas
        """
        print(f"🎼 ANALIZANDO GUSTOS MUSICALES PARA: {', '.join(user_artists)}")
        print("=" * 60)
        print()

        # CAPA 1: Análisis individual
        layer1 = {}
        for artist in user_artists:
            tracks = self.iconic_tracks.get(artist.lower(), [f"Popular {artist} track"])
            similar = self.superstars.get(artist.lower(), [f"Similar to {artist}"])
            layer1[artist] = {
                'tracks': tracks,
                'similar_artists': similar
            }

        # CAPA 2: Intersecciones entre listas
        layer2 = self._find_intersections(layer1, user_artists)

        # CAPA 3: Descubrimientos
        layer3 = self._generate_discoveries(layer2)

        # Resultado
        result = {
            'user_artists': user_artists,
            'layer1_analisis_individual': layer1,
            'layer2_intersecciones': layer2,
            'layer3_descubrimientos': layer3
        }

        self._display_results(result)
        return result

    def _find_intersections(self, layer1_data, user_artists):
        """Encuentra artistas comunes en las listas de similares"""
        intersections = []

        # Comparar cada par de artistas del usuario
        for i, artist_a in enumerate(user_artists):
            for artist_b in user_artists[i+1:]:
                similars_a = set(layer1_data[artist_a]['similar_artists'])
                similars_b = set(layer1_data[artist_b]['similar_artists'])

                common = similars_a & similars_b
                if common:
                    intersections.extend(common)

        # Remover duplicados
        return list(set(intersections))

    def _generate_discoveries(self, intersections):
        """Genera nuevos artistas para descubrir"""
        discoveries = []
        existing_artists = set()

        for inter_artist in intersections[:5]:  # Usar top 5
            # Simular encontrar artistas relacionados con este
            if '2pac' in inter_artist.lower():
                discoveries.extend(['Snoop Dogg', 'Ice Cube'])
            elif 'dr. dre' in inter_artist.lower():
                discoveries.extend(['Nate Dogg', 'The Game'])
            elif '50 cent' in inter_artist.lower():
                discoveries.extend(['Lloyd Banks', 'Tony Yayo'])
            elif 'iron maiden' in inter_artist.lower():
                discoveries.extend(['Dio', 'Rainbow'])
            elif 'black sabbath' in inter_artist.lower():
                discoveries.extend(['Heaven And Hell', 'Deep Purple'])

        return list(set(discoveries))[:3]  # Top 3 discoveries

    def _display_results(self, result):
        """Muestra los resultados de manera clara"""
        print("📊 RESULTADO DEL ANÁLISIS MULTI-CAPA:")
        print(f"👤 Tus artistas: {', '.join(result['user_artists'])}")
        print()

        # Layer 1
        print("🎤 CAPA 1 - ANÁLISIS INDIVIDUAL:")
        for artist, data in result['layer1_analisis_individual'].items():
            tracks = data['tracks']
            print(f"   {artist}: pistas icónicas --> {', '.join(tracks)}")
        print()

        # Layer 2
        print("🔄 CAPA 2 - INTERSECCIONES:")
        intersections = result['layer2_intersecciones']
        if intersections:
            print("   Artistas que conectan tus gustos:")
            for artist in intersections:
                print(f"   • {artist}")
        else:
            print("   No se encontraron intersecciones sólidas")
        print()

        # Layer 3
        print("🎨 CAPA 3 - DESCUBRIMIENTOS:")
        discoveries = result['layer3_descubrimientos']
        if discoveries:
            print("   Artistas nuevos para explorar:")
            for artist in discoveries:
                print(f"   • {artist}")
        else:
            print("   No se encontraron nuevos descubrimientos")
        print()

        print("✅ SISTEMA FUNCIONAL: Música Multi-Capa Disponible!")

async def main():
    """Demo del sistema"""
    recommender = MultiLayerMusicRecommender()

    # Ejemplo: Usuario que le gusta Eminem y luego agregó Metallica
    user_gustos = ["eminem", "metallica"]

    await recommender.recommend_multi_layer(user_gustos)

if __name__ == '__main__':
    asyncio.run(main())

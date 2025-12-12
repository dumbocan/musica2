export function DownloadsPage() {
  // Mock data based on actual downloads folder structure
  const downloadsData = [
    {
      artist: 'Eminem',
      tracks: ['Arose.mp3', 'Bad-Guy.mp3', 'Stan.mp3'],
      size: '~27.4MB',
      lastSync: '2 días'
    },
    {
      artist: 'Radiohead',
      tracks: [], // Would list actual tracks
      size: '~120MB',
      lastSync: '5 días'
    },
    {
      artist: 'Gorillaz',
      tracks: [],
      size: '~75MB',
      lastSync: '1 semana'
    },
    {
      artist: 'MGMT',
      tracks: [],
      size: '~98MB',
      lastSync: '3 días'
    },
    {
      artist: 'Franz Ferdinand',
      tracks: [],
      size: '~52MB',
      lastSync: '6 días'
    },
    {
      artist: 'Damon Albarn',
      tracks: [],
      size: '~45MB',
      lastSync: '1 semana'
    },
    {
      artist: 'Tally Hall',
      tracks: [],
      size: '~38MB',
      lastSync: '4 días'
    }
  ];

  return (
    <div style={{ padding: '24px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 'bold', marginBottom: '8px' }}>
          💿 Tus Descargas de Música
        </h1>
        <p style={{ color: '#666' }}>
          Archivos MP3 almacenados localmente en carpeta <code>downloads/</code>
        </p>
        <p style={{ color: '#666', fontSize: '14px', marginTop: '8px' }}>
          🎵 Música disponible offline - ¡independiente de internet!
        </p>
      </div>

      {/* Total Stats */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
        gap: '16px',
        marginBottom: '24px'
      }}>
        <div style={{
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
          padding: '16px',
          backgroundColor: 'white',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#3b82f6' }}>
            {downloadsData.length}
          </div>
          <div style={{ fontSize: '12px', color: '#666' }}>Artistas</div>
        </div>

        <div style={{
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
          padding: '16px',
          backgroundColor: 'white',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#06b6d4' }}>
            ~{downloadsData.filter(d => d.tracks.length > 0).reduce((sum, d) => sum + d.tracks.length, 0)}+
          </div>
          <div style={{ fontSize: '12px', color: '#666' }}>Canciones</div>
        </div>

        <div style={{
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
          padding: '16px',
          backgroundColor: 'white',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#7c3aed' }}>
            ~500MB
          </div>
          <div style={{ fontSize: '12px', color: '#666' }}>Espacio usado</div>
        </div>
      </div>

      {/* Downloads List */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
        gap: '20px'
      }}>
        {downloadsData.map((item, index) => (
          <div
            key={index}
            style={{
              border: '1px solid #e2e8f0',
              borderRadius: '12px',
              padding: '20px',
              backgroundColor: 'white',
              transition: 'transform 0.2s'
            }}
            onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
            onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0px)'}
          >
            {/* Artist Header */}
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{
                width: '48px',
                height: '48px',
                backgroundColor: '#f3f4f6',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginRight: '12px'
              }}>
                <span style={{ fontSize: '20px' }}>
                  {item.artist === 'Eminem' ? '🎤' :
                   item.artist === 'Radiohead' ? '📻' :
                   item.artist === 'Gorillaz' ? '🦍' :
                   item.artist === 'MGMT' ? '💊' :
                   item.artist === 'Franz Ferdinand' ? '🎵' :
                   item.artist === 'Damon Albarn' ? '🎸' : '🎵'}
                </span>
              </div>
              <div>
                <h3 style={{ fontSize: '18px', fontWeight: '600' }}>{item.artist}</h3>
                <p style={{ fontSize: '14px', color: '#666' }}>
                  {item.size} • {item.tracks.length > 0 ? `${item.tracks.length} canciones` : 'Colección completa'}
                </p>
              </div>
            </div>

            {/* Status */}
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              backgroundColor: '#dcfce7',
              color: '#166534',
              borderRadius: '20px',
              fontSize: '12px',
              fontWeight: '500',
              marginBottom: '16px'
            }}>
              <span>✅</span>
              <span>Archivos disponibles</span>
            </div>

            {/* Sample Tracks (if any) */}
            {item.tracks.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <p style={{ fontSize: '14px', fontWeight: '500', marginBottom: '8px' }}>
                  Ejemplos:
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {item.tracks.slice(0, 3).map((track, trackIndex) => (
                    <div key={trackIndex} style={{
                      fontSize: '12px',
                      color: '#666',
                      padding: '4px 8px',
                      backgroundColor: '#f8fafc',
                      borderRadius: '4px'
                    }}>
                      🎵 {track}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div style={{
              display: 'flex',
              gap: '8px',
              marginTop: 'auto'
            }}>
              <a
                href={`downloads/${item.artist.replace(/ /g, '-')}/`}
                target="_blank"
                rel="noopener"
                style={{
                  flex: 1,
                  textAlign: 'center',
                  padding: '8px 16px',
                  backgroundColor: '#3b82f6',
                  color: 'white',
                  textDecoration: 'none',
                  borderRadius: '6px',
                  fontSize: '14px',
                  fontWeight: '500',
                  transition: 'background-color 0.2s'
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#2563eb'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#3b82f6'}
              >
                📁 Explorar Archivos
              </a>
            </div>

            <p style={{
              fontSize: '12px',
              color: '#666',
              marginTop: '12px',
              textAlign: 'center'
            }}>
              Última sincronización: {item.lastSync} atrás
            </p>
          </div>
        ))}
      </div>

      {/* Bottom Info */}
      <div style={{
        marginTop: '32px',
        padding: '20px',
        border: '1px solid #e2e8f0',
        borderRadius: '12px',
        backgroundColor: '#f8fafc',
        textAlign: 'center'
      }}>
        <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '8px' }}>
          💾 Tu Música Local Segura
        </h3>
        <p style={{ fontSize: '14px', color: '#666', lineHeight: '1.5' }}>
          Todos estos archivos están guardados permanentemente en tu disco duro.<br/>
          🎶 ¡Disfruta tu música sin dependencias de internet ni servicios streaming!
        </p>
      </div>
    </div>
  );
}

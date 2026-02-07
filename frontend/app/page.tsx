'use client'

import { useState } from 'react'
import { useQuery } from 'react-query'
import axios from 'axios'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
})

export default function Dashboard() {
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)

  const { data: sites, refetch } = useQuery('sites', () => 
    api.get('/api/sites').then(r => r.data)
  )

  const generateSite = async () => {
    if (!keyword) return
    setLoading(true)
    await api.post('/api/sites/generate', {
      keyword,
      cloud_provider: 'aws',
      tone: 'professional'
    })
    setKeyword('')
    setLoading(false)
    refetch()
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white p-8">
      <h1 className="text-4xl font-bold mb-8">AutoSEO Dashboard</h1>
      
      <div className="bg-slate-900 p-6 rounded-lg mb-8">
        <h2 className="text-xl mb-4">Generate New Site</h2>
        <div className="flex gap-4">
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="Enter keyword (e.g., best coffee makers)"
            className="flex-1 px-4 py-2 rounded bg-slate-800 border border-slate-700"
          />
          <button
            onClick={generateSite}
            disabled={loading}
            className="px-6 py-2 bg-blue-600 rounded hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? 'Generating...' : 'Generate'}
          </button>
        </div>
      </div>

      <div className="grid gap-4">
        {sites?.map((site: any) => (
          <div key={site.id} className="bg-slate-900 p-4 rounded-lg flex justify-between items-center">
            <div>
              <h3 className="font-semibold">{site.domain}</h3>
              <p className="text-slate-400 text-sm">{site.keyword}</p>
              <span className={`text-xs px-2 py-1 rounded ${
                site.status === 'deployed' ? 'bg-green-900 text-green-300' :
                site.status === 'generating' ? 'bg-yellow-900 text-yellow-300' :
                'bg-slate-700 text-slate-300'
              }`}>
                {site.status}
              </span>
            </div>
            <div className="text-right">
              <p className="text-sm text-slate-400">SEO Score</p>
              <p className="text-2xl font-bold">{site.seo_score}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
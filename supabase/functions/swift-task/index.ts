// Supabase Edge Function: company-search (swift-task)
// view_company_dashboard 뷰에서 회사 검색 (Wreporter 위젯용)
// Params: q (query), eng (영문명 포함), fuzzy (유사 매칭)

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
}

const VIEW = 'view_company_dashboard'
const SELECT_COLS = 'corp_code, jurir_no, bizr_no, corp_name, corp_eng_name, corp_legal_name, ceo_nm, corp_cls, data_source, hm_url, induty_code, industry, emp_cnt, adres, est_dt, enp_main_biz_nm'

// 유사 검색: 글자 사이에 % 삽입 ("삼성전자" → "%삼%성%전%자%")
function fuzzyPattern(q: string): string {
  return '%' + q.split('').join('%') + '%'
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders })
  }

  try {
    const url = new URL(req.url)
    const query = url.searchParams.get('q')?.trim()
    const includeEng = url.searchParams.get('eng') === '1'
    const fuzzy = url.searchParams.get('fuzzy') === '1'

    if (!query || query.length < 2) {
      return new Response(
        JSON.stringify({ error: '검색어는 2자 이상 입력해주세요', results: [] }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    )

    let data: any[] = []

    if (fuzzy) {
      const fp = fuzzyPattern(query)
      let filterStr = `corp_name.ilike.${fp}`
      if (includeEng) filterStr += `,corp_eng_name.ilike.${fp}`

      const { data: fuzzyData, error } = await supabase
        .from(VIEW)
        .select(SELECT_COLS)
        .or(filterStr)
        .order('corp_cls', { ascending: false })
        .limit(15)

      if (error) throw error
      data = fuzzyData || []

    } else {
      const prefixPattern = `${query}%`
      const containsPattern = `%${query}%`

      let filterStr = `corp_name.ilike.${prefixPattern}`
      if (includeEng) filterStr += `,corp_eng_name.ilike.${prefixPattern}`

      const { data: prefixData, error: prefixErr } = await supabase
        .from(VIEW)
        .select(SELECT_COLS)
        .or(filterStr)
        .order('corp_cls', { ascending: false })
        .limit(10)

      if (prefixErr) throw prefixErr
      data = prefixData || []

      if (data.length < 5) {
        let containsFilter = `corp_name.ilike.${containsPattern}`
        if (includeEng) containsFilter += `,corp_eng_name.ilike.${containsPattern}`

        const prefixIds = new Set(data.map(d => d.jurir_no || d.corp_code))

        const { data: containsData, error: containsErr } = await supabase
          .from(VIEW)
          .select(SELECT_COLS)
          .or(containsFilter)
          .order('corp_cls', { ascending: false })
          .limit(20)

        if (!containsErr && containsData) {
          const extra = containsData.filter(c =>
            !prefixIds.has(c.jurir_no || c.corp_code)
          ).slice(0, 10 - data.length)
          data = [...data, ...extra]
        }
      }
    }

    const results = data.map(c => {
      let market_label: string
      if (c.corp_cls === 'Y') market_label = '코스피'
      else if (c.corp_cls === 'K') market_label = '코스닥'
      else if (c.corp_cls === 'N') market_label = '코넥스'
      else {
        market_label = c.corp_code ? '비상장(외감)' : '비상장(비외감)'
      }

      return {
        ...c,
        market_label,
        source_label: ({ dart: 'DART', fsc: 'FSC', both: 'DART+FSC' } as any)[c.data_source] || c.data_source,
        has_dart: c.corp_code !== null,
      }
    })

    return new Response(
      JSON.stringify({ results, count: results.length }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )

  } catch (err) {
    return new Response(
      JSON.stringify({ error: (err as Error).message, results: [] }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )
  }
})
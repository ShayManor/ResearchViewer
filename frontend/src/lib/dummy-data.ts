import type { Paper } from './api';

// ── Seed papers (20 landmark + many smaller) ─────────────────
export const SEED_PAPERS: Paper[] = [
  { doi: '1706.03762', title: 'Attention Is All You Need', abstract: 'We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.', authors: 'Vaswani, Shazeer, Parmar, Uszkoreit, Jones, Gomez, Kaiser, Polosukhin', categories: 'cs.CL cs.LG', citation_count: 95000, update_date: '2017-06-12' },
  { doi: '1810.04805', title: 'BERT: Pre-training of Deep Bidirectional Transformers', abstract: 'We introduce BERT for pre-training deep bidirectional representations.', authors: 'Devlin, Chang, Lee, Toutanova', categories: 'cs.CL', citation_count: 75000, update_date: '2018-10-11' },
  { doi: '1512.03385', title: 'Deep Residual Learning for Image Recognition', abstract: 'We present a residual learning framework for training deep networks.', authors: 'He, Zhang, Ren, Sun', categories: 'cs.CV', citation_count: 140000, update_date: '2015-12-10' },
  { doi: '1406.2661', title: 'Generative Adversarial Nets', abstract: 'We propose estimating generative models via an adversarial process.', authors: 'Goodfellow, Pouget-Abadie, Mirza, Xu, Warde-Farley, Ozair, Courville, Bengio', categories: 'cs.LG stat.ML', citation_count: 55000, update_date: '2014-06-10' },
  { doi: '1301.3781', title: 'Efficient Estimation of Word Representations in Vector Space', abstract: 'Two novel model architectures for word vector representations.', authors: 'Mikolov, Chen, Corrado, Dean', categories: 'cs.CL', citation_count: 35000, update_date: '2013-01-16' },
  { doi: '1409.1556', title: 'Very Deep Convolutional Networks (VGGNet)', abstract: 'Investigating effect of network depth on accuracy.', authors: 'Simonyan, Zisserman', categories: 'cs.CV', citation_count: 90000, update_date: '2014-09-04' },
  { doi: '1412.6980', title: 'Adam: A Method for Stochastic Optimization', abstract: 'First-order gradient-based optimization of stochastic objectives.', authors: 'Kingma, Ba', categories: 'cs.LG', citation_count: 120000, update_date: '2014-12-22' },
  { doi: '1409.0473', title: 'Neural Machine Translation by Jointly Learning to Align and Translate', abstract: 'Extending seq2seq by allowing search for relevant parts.', authors: 'Bahdanau, Cho, Bengio', categories: 'cs.CL cs.LG', citation_count: 25000, update_date: '2014-09-01' },
  { doi: '1607.06450', title: 'Layer Normalization', abstract: 'Layer normalization to address training issues.', authors: 'Ba, Kiros, Hinton', categories: 'cs.LG stat.ML', citation_count: 12000, update_date: '2016-07-21' },
  { doi: '2005.14165', title: 'Language Models are Few-Shot Learners (GPT-3)', abstract: 'Scaling up language models improves few-shot performance.', authors: 'Brown, Mann, Ryder, Subbiah, et al.', categories: 'cs.CL', citation_count: 28000, update_date: '2020-05-28' },
  { doi: '2010.11929', title: 'An Image is Worth 16x16 Words (ViT)', abstract: 'Pure transformer for image classification.', authors: 'Dosovitskiy, Beyer, Kolesnikov, et al.', categories: 'cs.CV cs.LG', citation_count: 18000, update_date: '2020-10-22' },
  { doi: '2103.00020', title: 'CLIP: Learning Transferable Visual Models', abstract: 'Contrastive pre-training on image-text pairs.', authors: 'Radford, Kim, Hallacy, Ramesh, et al.', categories: 'cs.CV cs.CL', citation_count: 14000, update_date: '2021-02-26' },
  { doi: '2112.10752', title: 'High-Resolution Image Synthesis with Latent Diffusion', abstract: 'Diffusion models in latent space.', authors: 'Rombach, Blattmann, Lorenz, Esser, Ommer', categories: 'cs.CV', citation_count: 9500, update_date: '2021-12-20' },
  { doi: '1503.02531', title: 'Distilling the Knowledge in a Neural Network', abstract: 'Improving smaller models by mimicking large ones.', authors: 'Hinton, Vinyals, Dean', categories: 'cs.LG stat.ML', citation_count: 11000, update_date: '2015-03-09' },
  { doi: '2303.08774', title: 'GPT-4 Technical Report', abstract: 'Large-scale multimodal model.', authors: 'OpenAI', categories: 'cs.CL cs.AI', citation_count: 7500, update_date: '2023-03-15' },
  { doi: '2302.13971', title: 'LLaMA: Open and Efficient Foundation Language Models', abstract: 'Foundation LMs from 7B to 65B on public data.', authors: 'Touvron, Lavril, Izacard, et al.', categories: 'cs.CL', citation_count: 5200, update_date: '2023-02-27' },
  { doi: '1711.05101', title: 'Neural Discrete Representation Learning (VQ-VAE)', abstract: 'Generative model with discrete representations.', authors: 'van den Oord, Vinyals, Kavukcuoglu', categories: 'cs.LG', citation_count: 4800, update_date: '2017-11-02' },
  { doi: '2006.11239', title: 'Denoising Diffusion Probabilistic Models', abstract: 'High quality image synthesis with diffusion.', authors: 'Ho, Jain, Abbeel', categories: 'cs.LG stat.ML', citation_count: 8200, update_date: '2020-06-19' },
  { doi: '1710.10903', title: 'Graph Attention Networks', abstract: 'Neural network architectures on graph-structured data.', authors: 'Veličković, Cucurull, Casanova, Romero, Liò, Bengio', categories: 'cs.LG stat.ML', citation_count: 11500, update_date: '2017-10-30' },
  { doi: '2305.18290', title: 'Direct Preference Optimization (DPO)', abstract: 'Directly optimizing policy from preference data.', authors: 'Rafailov, Sharma, Mitchell, Ermon, Manning, Finn', categories: 'cs.LG cs.AI', citation_count: 2100, update_date: '2023-05-29' },
  // Smaller papers — visible on zoom
  { doi: '1704.04861', title: 'MobileNets: Efficient CNNs for Mobile Vision', authors: 'Howard et al.', categories: 'cs.CV', citation_count: 14000, update_date: '2017-04-17' },
  { doi: '1905.11946', title: 'EfficientNet: Rethinking Model Scaling for CNNs', authors: 'Tan, Le', categories: 'cs.CV cs.LG', citation_count: 11000, update_date: '2019-05-28' },
  { doi: '2004.10934', title: 'YOLOv4: Optimal Speed and Accuracy', authors: 'Bochkovskiy et al.', categories: 'cs.CV', citation_count: 9000, update_date: '2020-04-23' },
  { doi: '1803.02999', title: 'The Lottery Ticket Hypothesis', authors: 'Frankle, Carlin', categories: 'cs.LG', citation_count: 4500, update_date: '2018-03-09' },
  { doi: '2002.05709', title: 'A Survey on Transfer Learning in NLP', authors: 'Ruder et al.', categories: 'cs.CL', citation_count: 2800, update_date: '2020-02-13' },
  { doi: '1901.02860', title: 'Transformer-XL: Attentive Language Models', authors: 'Dai et al.', categories: 'cs.CL cs.LG', citation_count: 3200, update_date: '2019-01-09' },
  { doi: '2106.09685', title: 'LoRA: Low-Rank Adaptation of LLMs', authors: 'Hu, Shen, Wallis et al.', categories: 'cs.CL cs.LG cs.AI', citation_count: 4100, update_date: '2021-06-17' },
  { doi: '2204.02311', title: 'PaLM: Scaling Language Modeling with Pathways', authors: 'Chowdhery et al.', categories: 'cs.CL', citation_count: 3000, update_date: '2022-04-05' },
  { doi: '2210.11416', title: 'Scaling Instruction-Finetuned Language Models (Flan-T5)', authors: 'Chung et al.', categories: 'cs.CL cs.AI', citation_count: 1800, update_date: '2022-10-20' },
  { doi: '1706.01427', title: 'Convolutional Sequence to Sequence Learning', authors: 'Gehring et al.', categories: 'cs.CL', citation_count: 2400, update_date: '2017-05-08' },
  { doi: '1910.01108', title: 'DistilBERT, a distilled version of BERT', authors: 'Sanh et al.', categories: 'cs.CL', citation_count: 3500, update_date: '2019-10-02' },
  { doi: '2203.15556', title: 'Training Compute-Optimal LLMs (Chinchilla)', authors: 'Hoffmann et al.', categories: 'cs.CL cs.LG', citation_count: 2200, update_date: '2022-03-29' },
  { doi: '1805.12471', title: 'Universal Language Model Fine-tuning (ULMFiT)', authors: 'Howard, Ruder', categories: 'cs.CL', citation_count: 2600, update_date: '2018-05-23' },
  { doi: '2305.14314', title: 'QLoRA: Efficient Finetuning of Quantized LLMs', authors: 'Dettmers et al.', categories: 'cs.LG cs.CL', citation_count: 1500, update_date: '2023-05-23' },
  { doi: '1711.00937', title: 'Mixup: Beyond Empirical Risk Minimization', authors: 'Zhang et al.', categories: 'cs.LG stat.ML', citation_count: 5500, update_date: '2017-11-03' },
  { doi: '2002.04745', title: 'SimCLR: Contrastive Learning of Visual Representations', authors: 'Chen et al.', categories: 'cs.CV cs.LG', citation_count: 7200, update_date: '2020-02-13' },
  { doi: '2011.10566', title: 'DALL-E: Creating Images from Text', authors: 'Ramesh et al.', categories: 'cs.CV cs.CL', citation_count: 4000, update_date: '2021-01-05' },
  { doi: '2307.09288', title: 'Llama 2: Open Foundation and Fine-Tuned Chat Models', authors: 'Touvron et al.', categories: 'cs.CL cs.AI', citation_count: 3800, update_date: '2023-07-18' },
];

// ── Citation links between papers (directed: source cites target) ─
export const PAPER_CITATIONS: { source: string; target: string; strength: number }[] = [
  // Transformer lineage
  { source: '1706.03762', target: '1409.0473', strength: 0.95 }, // Transformer ← Bahdanau attention
  { source: '1706.03762', target: '1607.06450', strength: 0.7 },  // Transformer ← LayerNorm
  { source: '1810.04805', target: '1706.03762', strength: 0.98 }, // BERT ← Transformer
  { source: '2005.14165', target: '1706.03762', strength: 0.95 }, // GPT-3 ← Transformer
  { source: '2005.14165', target: '1810.04805', strength: 0.6 },  // GPT-3 ← BERT
  { source: '2303.08774', target: '2005.14165', strength: 0.9 },  // GPT-4 ← GPT-3
  { source: '2303.08774', target: '1706.03762', strength: 0.85 }, // GPT-4 ← Transformer
  { source: '2302.13971', target: '2005.14165', strength: 0.8 },  // LLaMA ← GPT-3
  { source: '2302.13971', target: '1706.03762', strength: 0.85 },
  { source: '2307.09288', target: '2302.13971', strength: 0.95 }, // Llama2 ← LLaMA
  // Vision lineage
  { source: '1512.03385', target: '1409.1556', strength: 0.9 },   // ResNet ← VGG
  { source: '2010.11929', target: '1706.03762', strength: 0.95 }, // ViT ← Transformer
  { source: '2010.11929', target: '1512.03385', strength: 0.6 },  // ViT ← ResNet
  { source: '2103.00020', target: '2010.11929', strength: 0.85 }, // CLIP ← ViT
  { source: '2103.00020', target: '1810.04805', strength: 0.5 },  // CLIP ← BERT
  { source: '2112.10752', target: '1406.2661', strength: 0.7 },   // LDM ← GANs
  { source: '2112.10752', target: '2006.11239', strength: 0.95 }, // LDM ← DDPM
  { source: '2011.10566', target: '2010.11929', strength: 0.7 },  // DALL-E ← ViT
  { source: '2011.10566', target: '1711.05101', strength: 0.8 },  // DALL-E ← VQ-VAE
  // ML foundations
  { source: '1406.2661', target: '1412.6980', strength: 0.4 },    // GANs ← Adam (optimizer)
  { source: '1503.02531', target: '1512.03385', strength: 0.3 },  // Distill ← ResNet (used as teacher)
  { source: '1710.10903', target: '1706.03762', strength: 0.6 },  // GAT ← Transformer (attention)
  { source: '2006.11239', target: '1711.05101', strength: 0.5 },  // DDPM ← VQ-VAE
  { source: '2305.18290', target: '2005.14165', strength: 0.7 },  // DPO ← GPT-3
  { source: '2106.09685', target: '1706.03762', strength: 0.8 },  // LoRA ← Transformer
  { source: '2106.09685', target: '2005.14165', strength: 0.6 },  // LoRA ← GPT-3
  { source: '1910.01108', target: '1810.04805', strength: 0.95 }, // DistilBERT ← BERT
  { source: '1910.01108', target: '1503.02531', strength: 0.8 },  // DistilBERT ← Distillation
  { source: '1901.02860', target: '1706.03762', strength: 0.9 },  // TransformerXL ← Transformer
  { source: '1905.11946', target: '1512.03385', strength: 0.6 },  // EfficientNet ← ResNet
  { source: '1704.04861', target: '1512.03385', strength: 0.5 },  // MobileNet ← ResNet
  { source: '2002.04745', target: '1512.03385', strength: 0.7 },  // SimCLR ← ResNet
  { source: '2305.14314', target: '2106.09685', strength: 0.95 }, // QLoRA ← LoRA
  { source: '2203.15556', target: '2005.14165', strength: 0.85 }, // Chinchilla ← GPT-3
  { source: '2210.11416', target: '1810.04805', strength: 0.6 },  // Flan-T5 ← BERT
  { source: '2204.02311', target: '2005.14165', strength: 0.9 },  // PaLM ← GPT-3
];

// ── User profile ─────────────────────────────────────────────
export interface UserProfileData {
  username: string;
  email: string;
  linkedAuthorId: string | null;
  linkedAuthorName: string | null;
  joinDate: string;
  readingList: string[];
  readHistory: { doi: string; readDate: string }[];
  focusTopics: string[];
  publications: Publication[];
}

export interface Publication {
  doi: string;
  title: string;
  venue: string;
  year: number;
  citations: number;
  coauthors: string[];
}

export const DUMMY_USER: UserProfileData = {
  username: 'Shay',
  email: 'shay@purdue.edu',
  linkedAuthorId: null,
  linkedAuthorName: null,
  joinDate: '2024-09-01',
  readingList: [
    '1706.03762', '1810.04805', '1512.03385', '1406.2661',
    '1301.3781', '1409.1556', '2303.08774', '2106.09685',
    '1503.02531', '2305.18290', '2010.11929',
  ],
  readHistory: [
    { doi: '1706.03762', readDate: '2024-09-15' },
    { doi: '1512.03385', readDate: '2024-09-20' },
    { doi: '1409.1556', readDate: '2024-09-22' },
    { doi: '1406.2661', readDate: '2024-10-01' },
    { doi: '1301.3781', readDate: '2024-10-08' },
    { doi: '1810.04805', readDate: '2024-10-15' },
    { doi: '1503.02531', readDate: '2024-11-02' },
    { doi: '2303.08774', readDate: '2024-11-20' },
    { doi: '2010.11929', readDate: '2024-12-05' },
    { doi: '2106.09685', readDate: '2025-01-10' },
    { doi: '2305.18290', readDate: '2025-02-01' },
  ],
  focusTopics: ['cs.LG', 'cs.CV', 'cs.CL'],
  publications: [
    { doi: 'shay/2025-guardrail', title: 'Guardrail-Aware Knowledge Distillation for Semantic Segmentation', venue: 'Under Review', year: 2025, citations: 0, coauthors: ['Bera, A.'] },
    { doi: 'shay/2024-gpufindr', title: 'gpufindr: Real-Time GPU Cloud Price Aggregation', venue: 'Side Project', year: 2024, citations: 0, coauthors: [] },
    { doi: 'shay/2025-iquhack', title: 'GPU-Accelerated Quantum VaR Estimation', venue: 'iQuHACK 2025 (Grand Prize)', year: 2025, citations: 0, coauthors: [] },
  ],
};

// ── Topic structure ──────────────────────────────────────────
export interface TopicNode {
  id: string;
  label: string;
  fullLabel: string;
  paperCount: number;
  avgCitations: number;
  totalCitations: number;
  topPaperDois: string[];
  citationsOverTime: { year: string; count: number; citations: number }[];
  recentGrowth: number; // papers in last 2 years vs total
}

export interface TopicEdge {
  source: string;
  target: string;
  weight: number;
  sharedPaperCount: number;
}

const TOPIC_LABELS: Record<string, string> = {
  'cs.CL': 'NLP', 'cs.LG': 'Machine Learning', 'cs.CV': 'Computer Vision',
  'cs.AI': 'Artificial Intelligence', 'stat.ML': 'Statistical ML',
};

export function buildTopicGraph(): { nodes: TopicNode[]; edges: TopicEdge[] } {
  const topicPapers = new Map<string, Paper[]>();
  for (const p of SEED_PAPERS) {
    for (const cat of (p.categories || '').split(/\s+/).filter(Boolean)) {
      if (!topicPapers.has(cat)) topicPapers.set(cat, []);
      topicPapers.get(cat)!.push(p);
    }
  }

  const nodes: TopicNode[] = [];
  for (const [topic, papers] of topicPapers) {
    const sorted = [...papers].sort((a, b) => (b.citation_count || 0) - (a.citation_count || 0));
    const totalCit = papers.reduce((s, p) => s + (p.citation_count || 0), 0);

    // Build citations over time
    const yearMap = new Map<string, { count: number; citations: number }>();
    for (const p of papers) {
      const y = p.update_date?.slice(0, 4) || 'Unknown';
      const e = yearMap.get(y) || { count: 0, citations: 0 };
      e.count++;
      e.citations += p.citation_count || 0;
      yearMap.set(y, e);
    }
    const citOverTime = Array.from(yearMap.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([year, data]) => ({ year, ...data }));

    const recentPapers = papers.filter(p => (p.update_date || '') >= '2022-01-01').length;

    nodes.push({
      id: topic, label: TOPIC_LABELS[topic] || topic, fullLabel: topic,
      paperCount: papers.length, avgCitations: Math.round(totalCit / papers.length),
      totalCitations: totalCit,
      topPaperDois: sorted.slice(0, 15).map(p => p.doi),
      citationsOverTime: citOverTime,
      recentGrowth: papers.length > 0 ? recentPapers / papers.length : 0,
    });
  }

  // Edges with variable weights
  const edges: TopicEdge[] = [];
  const keys = Array.from(topicPapers.keys());
  for (let i = 0; i < keys.length; i++) {
    for (let j = i + 1; j < keys.length; j++) {
      const aSet = new Set(topicPapers.get(keys[i])!.map(p => p.doi));
      const bSet = new Set(topicPapers.get(keys[j])!.map(p => p.doi));
      let inter = 0;
      for (const d of aSet) if (bSet.has(d)) inter++;

      // Also count cross-citations between the two topic's papers
      let crossCites = 0;
      for (const c of PAPER_CITATIONS) {
        const sInA = aSet.has(c.source), sInB = bSet.has(c.source);
        const tInA = aSet.has(c.target), tInB = bSet.has(c.target);
        if ((sInA && tInB) || (sInB && tInA)) crossCites++;
      }

      const union = aSet.size + bSet.size - inter;
      const jaccard = union > 0 ? inter / union : 0;
      const citWeight = crossCites / Math.max(PAPER_CITATIONS.length * 0.1, 1);
      const weight = jaccard * 0.4 + citWeight * 0.6; // citation links matter more
      if (weight > 0.02) {
        edges.push({ source: keys[i], target: keys[j], weight: Math.min(weight, 1), sharedPaperCount: inter });
      }
    }
  }

  return { nodes, edges };
}

// ── Paper-level graph for zoom detail ────────────────────────
export interface PaperNode {
  doi: string;
  title: string;
  shortTitle: string;
  category: string;
  citationCount: number;
  year: string;
  tier: 'landmark' | 'notable' | 'standard'; // determines zoom visibility
}

export function buildPaperNodes(): PaperNode[] {
  return SEED_PAPERS.map(p => {
    const cc = p.citation_count || 0;
    const tier = cc >= 25000 ? 'landmark' : cc >= 5000 ? 'notable' : 'standard';
    const shortTitle = p.title.length > 40 ? p.title.slice(0, 37) + '…' : p.title;
    return {
      doi: p.doi, title: p.title, shortTitle,
      category: (p.categories || '').split(/\s+/)[0] || 'unknown',
      citationCount: cc, year: (p.update_date || '').slice(0, 4), tier,
    };
  });
}

// ── Hot papers ───────────────────────────────────────────────
export const HOT_PAPERS: Paper[] = SEED_PAPERS
  .filter(p => (p.update_date || '') >= '2021-01-01')
  .sort((a, b) => (b.citation_count || 0) - (a.citation_count || 0))
  .slice(0, 6);

// ── Paper velocity (simulated weekly) ────────────────────────
export const PAPER_VELOCITY = [
  { week: 'Jan 1', count: 312 }, { week: 'Jan 8', count: 287 },
  { week: 'Jan 15', count: 345 }, { week: 'Jan 22', count: 401 },
  { week: 'Jan 29', count: 378 }, { week: 'Feb 5', count: 356 },
  { week: 'Feb 12', count: 423 }, { week: 'Feb 19', count: 389 },
  { week: 'Feb 26', count: 412 }, { week: 'Mar 5', count: 467 },
  { week: 'Mar 12', count: 445 }, { week: 'Mar 19', count: 502 },
];

// ── Recommendations ──────────────────────────────────────────
export function getRecommendations(readDois: string[]): Paper[] {
  const readSet = new Set(readDois);
  const readCats = new Set<string>();
  for (const doi of readDois) {
    const p = SEED_PAPERS.find(sp => sp.doi === doi);
    if (p) for (const c of (p.categories || '').split(/\s+/)) readCats.add(c);
  }
  // Also boost papers that are cited by or cite papers in reading list
  const citedByRead = new Set<string>();
  const citesRead = new Set<string>();
  for (const c of PAPER_CITATIONS) {
    if (readSet.has(c.source)) citedByRead.add(c.target);
    if (readSet.has(c.target)) citesRead.add(c.source);
  }

  return SEED_PAPERS
    .filter(p => !readSet.has(p.doi))
    .map(p => {
      const cats = (p.categories || '').split(/\s+/);
      const catOverlap = cats.filter(c => readCats.has(c)).length;
      const citBonus = (citedByRead.has(p.doi) ? 500 : 0) + (citesRead.has(p.doi) ? 300 : 0);
      return { paper: p, score: catOverlap * 1000 + citBonus + (p.citation_count || 0) / 100 };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 8)
    .map(x => x.paper);
}

export function getSeedPaper(doi: string): Paper | undefined {
  return SEED_PAPERS.find(p => p.doi === doi);
}

export function getPapersForTopic(topicId: string): Paper[] {
  return SEED_PAPERS
    .filter(p => (p.categories || '').split(/\s+/).includes(topicId))
    .sort((a, b) => (b.citation_count || 0) - (a.citation_count || 0));
}

// ── User reading stats ───────────────────────────────────────
export function getUserReadingStats(user: UserProfileData) {
  const byTopic: Record<string, number> = {};
  const byMonth: Record<string, number> = {};

  for (const entry of user.readHistory) {
    const paper = getSeedPaper(entry.doi);
    if (paper) {
      for (const cat of (paper.categories || '').split(/\s+/).filter(Boolean)) {
        byTopic[cat] = (byTopic[cat] || 0) + 1;
      }
    }
    const month = entry.readDate.slice(0, 7);
    byMonth[month] = (byMonth[month] || 0) + 1;
  }

  const topicEntries = Object.entries(byTopic).sort((a, b) => b[1] - a[1]);
  const monthEntries = Object.entries(byMonth).sort((a, b) => a[0].localeCompare(b[0]));

  const totalCitationsRead = user.readingList.reduce((s, doi) => {
    const p = getSeedPaper(doi);
    return s + (p?.citation_count || 0);
  }, 0);

  return { byTopic: topicEntries, byMonth: monthEntries, totalCitationsRead };
}

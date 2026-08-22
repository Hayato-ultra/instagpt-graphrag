import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { Calendar, Clock, Tag, ArrowRight, BookOpen, ExternalLink } from 'lucide-react'

const posts = [
  {
    slug: 'introducing-instagpt-v2',
    title: 'Introducing InstaGPT v2.0: The Automated Knowledge Pipeline',
    excerpt: 'Our biggest update yet brings automated enrichment, semantic search, and multi-modal processing to every knowledge graph.',
    category: 'Product',
    date: '2024-12-15',
    readTime: '8 min',
    author: 'Sarah Chen',
  },
  {
    slug: 'graphrag-vs-rag',
    title: 'GraphRAG vs Traditional RAG: Why Structure Matters',
    excerpt: 'A deep dive into why knowledge graphs outperform vector-only retrieval for complex reasoning tasks.',
    category: 'Engineering',
    date: '2024-11-28',
    readTime: '12 min',
    author: 'Marcus Webb',
  },
  {
    slug: 'building-knowledge-graphs-at-scale',
    title: 'Building Knowledge Graphs at Scale: Lessons from 10M+ Entities',
    excerpt: 'Architecture patterns, database choices, and optimization strategies we learned running InstaGPT in production.',
    category: 'Engineering',
    date: '2024-10-15',
    readTime: '15 min',
    author: 'Priya Patel',
  },
  {
    slug: 'semantic-search-best-practices',
    title: 'Semantic Search Best Practices for Knowledge Graphs',
    excerpt: 'How to design effective semantic search over structured knowledge — query understanding, reranking, and evidence citation.',
    category: 'Product',
    date: '2024-09-20',
    readTime: '10 min',
    author: 'James Liu',
  },
  {
    slug: 'multi-modal-extraction',
    title: 'Multi-Modal Entity Extraction from Video Content',
    excerpt: 'Technical breakdown of our pipeline: Whisper v3 transcription, keyframe extraction, OCR, and entity resolution.',
    category: 'Research',
    date: '2024-08-10',
    readTime: '18 min',
    author: 'Sarah Chen',
  },
  {
    slug: 'privacy-first-ai',
    title: 'Privacy-First AI: Building GraphRAG Without Data Leakage',
    excerpt: 'Our approach to end-to-end encryption, zero-trust architecture, and compliance without compromising capability.',
    category: 'Engineering',
    date: '2024-07-01',
    readTime: '11 min',
    author: 'Marcus Webb',
  },
]

const categories = ['All', 'Product', 'Engineering', 'Research', 'Company']

export default function BlogPage() {
  return (
    <div className="min-h-screen bg-background">
      <nav className="fixed top-0 w-full z-50 bg-surface-container/80 backdrop-blur-md border-b border-outline-variant/10">
        <div className="flex justify-between items-center max-w-container-max mx-auto px-md h-20">
          <Link to="/" className="font-h1 text-h1 text-primary flex items-center gap-2">
            <span className="material-symbols-outlined" data-icon="hub">hub</span>
            InstaGPT
          </Link>
          <div className="hidden md:flex items-center gap-8 font-body-md text-body-md">
            <Link className="text-on-surface-variant hover:text-primary transition-colors" to="/">Home</Link>
            <Link className="text-on-surface-variant hover:text-primary transition-colors" to="/about">About</Link>
            <Link className="text-on-surface-variant hover:text-primary transition-colors" to="/services">Services</Link>
            <Link className="text-primary font-bold" to="/blog">Blog</Link>
          </div>
          <Link to="/analyze" className="bg-inverse-primary hover:bg-primary-container text-white px-6 py-2 rounded font-body-md transition-all">
            Get Started
          </Link>
        </div>
      </nav>

      <main className="pt-32">
        {/* Hero */}
        <motion.section
          className="relative max-w-container-max mx-auto px-md py-24 border-x border-surface-variant/30 text-center"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <motion.div
            className="inline-flex items-center gap-2 px-3 py-1 mb-6 rounded-full border border-surface-variant bg-surface-container-low text-on-surface-variant font-label-sm uppercase tracking-wider"
          >
            <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
            InstaGPT Blog
          </motion.div>

          <motion.h1
            className="font-display text-display md:text-display text-on-surface mb-6 max-w-3xl mx-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            Insights on <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-inverse-primary">
              GraphRAG, AI & Knowledge Engineering.
            </span>
          </motion.h1>

          <motion.p
            className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mx-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            Deep dives into our technology, product updates, and lessons learned building the future of knowledge graphs.
          </motion.p>
        </motion.section>

        {/* Category Filter */}
        <motion.section
          className="max-w-container-max mx-auto px-md py-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <div className="flex flex-wrap gap-3 justify-center">
            {categories.map((cat) => (
              <button
                key={cat}
                className={`px-4 py-2 rounded-full font-label-sm text-label-sm transition-all ${
                  cat === 'All'
                    ? 'bg-primary text-white'
                    : 'bg-surface-container-high border border-outline-variant text-on-surface-variant hover:border-primary/50 hover:text-primary'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </motion.section>

        {/* Posts Grid */}
        <motion.section
          className="max-w-container-max mx-auto px-md pb-24"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {posts.map((post, i) => (
              <motion.article
                key={post.slug}
                className="glass-panel p-6 rounded-xl border border-surface-variant/50 hover:border-primary/30 transition-colors flex flex-col group"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 * i }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <span className="font-mono text-[11px] px-2 py-1 rounded bg-primary/10 text-primary border border-primary/20 uppercase">
                    {post.category}
                  </span>
                  <span className="font-mono text-[11px] text-on-surface-variant flex items-center gap-1">
                    <Calendar size={12} />
                    {new Date(post.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </span>
                </div>
                <Link to={`/blog/${post.slug}`} className="group">
                  <h2 className="font-h2 text-h2 text-on-surface mb-3 group-hover:text-primary transition-colors line-clamp-2">
                    {post.title}
                  </h2>
                </Link>
                <p className="font-body-md text-body-md text-on-surface-variant mb-4 flex-1 line-clamp-3">
                  {post.excerpt}
                </p>
                <div className="flex items-center justify-between pt-4 border-t border-outline-variant">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center font-label-sm text-label-sm text-primary border border-primary/20">
                      {post.author.split(' ').map(n => n[0]).join('')}
                    </div>
                    <span className="font-body-md text-body-md text-on-surface-variant">{post.author}</span>
                  </div>
                  <Link to={`/blog/${post.slug}`} className="font-label-sm text-label-sm text-primary hover:underline flex items-center gap-1">
                    Read more
                    <ArrowRight size={14} />
                  </Link>
                </div>
              </motion.article>
            ))}
          </div>

          {/* Load More */}
          <motion.div
            className="text-center mt-12"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.5 }}
          >
            <button className="border border-surface-variant text-on-surface px-8 py-3 rounded font-body-md hover:bg-surface-container transition-colors">
              Load More Articles
            </button>
          </motion.div>
        </motion.section>

        {/* Newsletter */}
        <motion.section
          className="max-w-container-max mx-auto px-md py-16 border-y border-surface-variant/30"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <div className="max-w-2xl mx-auto text-center">
            <h2 className="font-h1 text-h1 text-on-surface mb-4">Stay Updated</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant mb-8">
              Get the latest GraphRAG research, product updates, and engineering insights delivered weekly.
            </p>
            <form className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <input
                type="email"
                placeholder="your@email.com"
                className="flex-1 bg-surface-container-high border border-outline-variant rounded-lg px-4 py-3 text-on-background font-body-md placeholder:text-outline focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
              <button className="bg-inverse-primary text-white px-6 py-3 rounded font-body-md hover:bg-primary-container transition-all whitespace-nowrap">
                Subscribe
              </button>
            </form>
            <p className="font-mono text-mono text-on-surface-variant mt-4 text-xs">No spam. Unsubscribe anytime.</p>
          </div>
        </motion.section>
      </main>

      <footer className="w-full bg-surface border-t border-outline-variant py-12">
        <div className="max-w-container-max mx-auto px-md text-center">
          <p className="font-body-md text-body-md text-on-surface-variant">© 2024 InstaGPT Inc. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
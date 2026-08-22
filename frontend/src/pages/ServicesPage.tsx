import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { ArrowRight, Check, Zap, Database, Search, Globe, Brain, Shield, Code2, Layers, Activity } from 'lucide-react'

const plans = [
  {
    name: 'Starter',
    price: '$0',
    period: '/month',
    desc: 'Perfect for individual researchers and students',
    features: [
      '10 analyses/month',
      '1,000 entities',
      'Basic semantic search',
      'Export to JSON/CSV',
      'Community support',
    ],
    cta: 'Start Free',
    popular: false,
  },
  {
    name: 'Professional',
    price: '$49',
    period: '/month',
    desc: 'For power users and small teams',
    features: [
      'Unlimited analyses',
      '100,000 entities',
      'Advanced semantic search',
      'Graph visualization API',
      'Webhook integrations',
      'Priority email support',
      'Custom entity types',
    ],
    cta: 'Get Started',
    popular: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    desc: 'For organizations with advanced needs',
    features: [
      'Everything in Professional',
      'Unlimited entities & analyses',
      'On-premise deployment',
      'SSO/SAML authentication',
      'Dedicated support engineer',
      'SLA guarantee',
      'Custom model fine-tuning',
      'Audit logs & compliance',
    ],
    cta: 'Contact Sales',
    popular: false,
  },
]

const services = [
  {
    icon: Zap,
    title: 'URL-to-Graph Pipeline',
    desc: 'Automated extraction from Instagram Reels, YouTube, Wikipedia, Medium, LinkedIn, and custom URLs. Multi-modal processing: video, audio, OCR, and text.',
    features: ['Real-time processing', 'Multi-modal support', '14+ content types', 'Webhook notifications'],
  },
  {
    icon: Brain,
    title: 'Semantic Search & QA',
    desc: 'Natural language queries over your knowledge graph. Vector embeddings with evidence-backed answers and citation tracking.',
    features: ['Natural language queries', 'Evidence citations', 'Confidence scoring', 'Query history'],
  },
  {
    icon: Database,
    title: 'Knowledge Graph Explorer',
    desc: 'Interactive graph visualization with ReactFlow. Node inspection, relationship traversal, filtering, and export capabilities.',
    features: ['Interactive visualization', 'Node detail panels', 'Advanced filtering', 'Graph algorithms'],
  },
  {
    icon: Layers,
    title: 'Automated Enrichment',
    desc: 'Cross-reference entities automatically. Crawl linked citations, resolve conflicts, and build interconnected databases without manual entry.',
    features: ['Auto entity linking', 'Citation crawling', 'Conflict resolution', 'Continuous updates'],
  },
  {
    icon: Shield,
    title: 'Privacy & Compliance',
    desc: 'End-to-end encryption, data sovereignty, SOC 2 Type II, GDPR, HIPAA compliance. Your knowledge, your control.',
    features: ['E2E encryption', 'SOC 2 / GDPR / HIPAA', 'On-premise option', 'Audit trails'],
  },
  {
    icon: Code2,
    title: 'Developer Platform',
    desc: 'REST & GraphQL APIs, SDKs for Python/TypeScript, webhooks, custom integrations. Build AI-powered apps on your knowledge graph.',
    features: ['REST + GraphQL', 'Python/TS SDKs', 'Webhooks', 'Custom functions'],
  },
]

export default function ServicesPage() {
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
            <Link className="text-primary font-bold" to="/services">Services</Link>
            <Link className="text-on-surface-variant hover:text-primary transition-colors" to="/blog">Blog</Link>
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
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
            Products & Pricing
          </motion.div>

          <motion.h1
            className="font-display text-display md:text-display text-on-surface mb-6 max-w-3xl mx-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            Choose the right plan for your <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-inverse-primary">
              knowledge workflow.
            </span>
          </motion.h1>

          <motion.p
            className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mx-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            Every plan includes our core GraphRAG engine. Scale up as your knowledge grows.
          </motion.p>
        </motion.section>

        {/* Pricing */}
        <motion.section
          className="max-w-container-max mx-auto px-md py-12"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {plans.map((plan, i) => (
              <motion.div
                key={plan.name}
                className={`relative layer-1 rounded-xl p-lg flex flex-col ${plan.popular ? 'border-primary/50 ring-1 ring-primary/20' : 'border-surface-variant hover:border-primary/30'}`}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 * i }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-white px-3 py-1 rounded-full font-label-sm text-label-sm">
                    Most Popular
                  </div>
                )}
                <div className="mb-6">
                  <h3 className="font-h2 text-h2 text-on-surface mb-2">{plan.name}</h3>
                  <p className="font-body-md text-body-md text-on-surface-variant">{plan.desc}</p>
                </div>
                <div className="mb-6 flex items-baseline gap-1">
                  <span className="font-display text-display text-on-surface">{plan.price}</span>
                  <span className="font-body-md text-body-md text-on-surface-variant">{plan.period}</span>
                </div>
                <ul className="flex-1 space-y-3 mb-8">
                  {plan.features.map((feature, j) => (
                    <li key={j} className="flex items-center gap-3 font-body-md text-body-md text-on-surface-variant">
                      <Check size={18} className="text-secondary flex-shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <Link
                  to={plan.popular ? '/analyze' : '/contact'}
                  className={`w-full text-center py-3 rounded-lg font-body-md font-medium transition-all ${
                    plan.popular
                      ? 'bg-inverse-primary text-white hover:bg-primary-container'
                      : 'border border-surface-variant text-on-surface hover:bg-surface-container'
                  }`}
                >
                  {plan.cta}
                </Link>
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* Services Detail */}
        <motion.section
          className="max-w-container-max mx-auto px-md py-12 border-y border-surface-variant/30"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <motion.div
            className="text-center mb-16"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <span className="font-label-sm text-label-sm text-primary uppercase tracking-widest mb-4 block">Capabilities</span>
            <h2 className="font-h1 text-h1 text-on-surface mb-4">What You Can Build</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl mx-auto">
              Six core capabilities that power every InstaGPT deployment.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {services.map((service, i) => (
              <motion.div
                key={service.title}
                className="glass-panel p-8 rounded-lg border border-surface-variant/50 hover:border-primary/30 transition-colors group"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 * i }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
              >
                <motion.div
                  className="w-12 h-12 rounded bg-primary/10 flex items-center justify-center mb-6 border border-primary/20 text-primary group-hover:scale-105 group-hover:rotate-3 transition-transform"
                >
                  <service.icon size={24} />
                </motion.div>
                <h3 className="font-h2 text-h2 text-on-surface mb-3">{service.title}</h3>
                <p className="font-body-md text-body-md text-on-surface-variant mb-6">{service.desc}</p>
                <div className="flex flex-wrap gap-2">
                  {service.features.map((feature, j) => (
                    <span key={j} className="font-mono text-[11px] px-2 py-1 rounded bg-surface-variant text-on-surface border border-outline-variant">
                      {feature}
                    </span>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* Enterprise */}
        <motion.section
          className="max-w-container-max mx-auto px-md py-24 text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <motion.div
            className="max-w-3xl mx-auto p-12 layer-1 rounded-xl border border-primary/30"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h2 className="font-h1 text-h1 text-on-surface mb-4">Need Enterprise-Grade?</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant mb-8">
              Custom deployments, dedicated support, compliance packages, and volume discounts. Let&apos;s discuss your requirements.
            </p>
            <Link to="/contact" className="bg-inverse-primary text-white px-8 py-3 rounded font-body-md hover:bg-primary-container transition-all inline-flex items-center gap-2">
              Contact Sales
              <ArrowRight size={20} />
            </Link>
          </motion.div>
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
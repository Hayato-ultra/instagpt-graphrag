import { motion } from 'framer-motion'
import { Link, useFormStatus } from 'react-router-dom'
import { Mail, MessageSquare, MapPin, Github, Twitter, Linkedin, Send, Loader2 } from 'lucide-react'

const contactInfo = [
  { icon: Mail, title: 'Email', value: 'hello@instagpt.ai', href: 'mailto:hello@instagpt.ai' },
  { icon: MessageSquare, title: 'Discord', value: 'discord.gg/instagpt', href: 'https://discord.gg/instagpt' },
  { icon: MapPin, title: 'Location', value: 'San Francisco, CA', href: null },
  { icon: Github, title: 'GitHub', value: 'github.com/instagpt', href: 'https://github.com/instagpt' },
  { icon: Twitter, title: 'Twitter', value: '@instagpt', href: 'https://twitter.com/instagpt' },
  { icon: Linkedin, title: 'LinkedIn', value: 'InstaGPT', href: 'https://linkedin.com/company/instagpt' },
]

const faqs = [
  { q: 'How does the free tier work?', a: 'The free tier includes 10 analyses per month with up to 1,000 entities. No credit card required.' },
  { q: 'Can I deploy on-premise?', a: 'Yes, enterprise plans include on-premise deployment with full air-gapped support.' },
  { q: 'What data sources are supported?', a: 'Instagram Reels, YouTube, Wikipedia, Medium, LinkedIn, GitHub, and any public URL.' },
  { q: 'Is my data private?', a: 'Yes. End-to-end encryption, zero data sharing, and full data sovereignty. SOC 2, GDPR, HIPAA compliant.' },
  { q: 'How accurate is the extraction?', a: '99.2% entity accuracy with confidence scoring on every node. Evidence citations included.' },
]

export default function ContactPage() {
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
            <Link className="text-on-surface-variant hover:text-primary transition-colors" to="/blog">Blog</Link>
            <Link className="text-primary font-bold" to="/contact">Contact</Link>
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
            Get in Touch
          </motion.div>

          <motion.h1
            className="font-display text-display md:text-display text-on-surface mb-6 max-w-3xl mx-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            Let&apos;s build something <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-inverse-primary">
              intelligent together.
            </span>
          </motion.h1>

          <motion.p
            className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mx-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            Have questions about our platform? Need enterprise pricing? Want to partner with us? We&apos;d love to hear from you.
          </motion.p>
        </motion.section>

        {/* Contact Grid */}
        <motion.section
          className="max-w-container-max mx-auto px-md py-12"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Contact Form */}
            <motion.div
              className="lg:col-span-2 glass-panel p-8 rounded-xl border border-surface-variant/50"
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              <h2 className="font-h2 text-h2 text-on-surface mb-6">Send us a message</h2>
              <form className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="font-label-sm text-label-sm text-on-surface-variant block mb-2">Name</label>
                    <input
                      type="text"
                      className="w-full bg-surface-container-high border border-outline-variant rounded-lg px-4 py-3 text-on-background font-body-md placeholder:text-outline focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors"
                      placeholder="Your name"
                      required
                    />
                  </div>
                  <div>
                    <label className="font-label-sm text-label-sm text-on-surface-variant block mb-2">Email</label>
                    <input
                      type="email"
                      className="w-full bg-surface-container-high border border-outline-variant rounded-lg px-4 py-3 text-on-background font-body-md placeholder:text-outline focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors"
                      placeholder="you@example.com"
                      required
                    />
                  </div>
                </div>
                <div>
                  <label className="font-label-sm text-label-sm text-on-surface-variant block mb-2">Company (Optional)</label>
                  <input
                    type="text"
                    className="w-full bg-surface-container-high border border-outline-variant rounded-lg px-4 py-3 text-on-background font-body-md placeholder:text-outline focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors"
                    placeholder="Your company"
                  />
                </div>
                <div>
                  <label className="font-label-sm text-label-sm text-on-surface-variant block mb-2">How can we help?</label>
                  <select className="w-full bg-surface-container-high border border-outline-variant rounded-lg px-4 py-3 text-on-background font-body-md focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors">
                    <option value="">Select a topic</option>
                    <option value="sales">Sales & Pricing</option>
                    <option value="support">Technical Support</option>
                    <option value="partnership">Partnership</option>
                    <option value="press">Press & Media</option>
                    <option value="careers">Careers</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="font-label-sm text-label-sm text-on-surface-variant block mb-2">Message</label>
                  <textarea
                    rows={5}
                    className="w-full bg-surface-container-high border border-outline-variant rounded-lg px-4 py-3 text-on-background font-body-md placeholder:text-outline focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors resize-none"
                    placeholder="Tell us more about your needs..."
                    required
                  />
                </div>
                <button
                  type="submit"
                  className="w-full bg-inverse-primary text-white py-3 rounded-lg font-body-md font-medium hover:bg-primary-container transition-all flex items-center justify-center gap-2"
                >
                  <Send size={20} />
                  Send Message
                </button>
              </form>
            </motion.div>

            {/* Contact Info */}
            <motion.div
              className="space-y-6"
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
            >
              <motion.div
                className="glass-panel p-8 rounded-xl border border-surface-variant/50"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 }}
              >
                <h2 className="font-h2 text-h2 text-on-surface mb-6">Other ways to connect</h2>
                <div className="space-y-4">
                  {contactInfo.map((item) => (
                    <a
                      key={item.title}
                      href={item.href || '#'}
                      className="flex items-center gap-4 p-4 layer-1 rounded-lg hover:border-primary/30 transition-colors"
                      target={item.href ? '_blank' : undefined}
                      rel={item.href ? 'noopener noreferrer' : undefined}
                    >
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center border border-primary/20 text-primary">
                        <item.icon size={20} />
                      </div>
                      <div>
                        <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">{item.title}</p>
                        <p className="font-body-md text-body-md text-on-surface">{item.value}</p>
                      </div>
                    </a>
                  ))}
                </div>
              </motion.div>

              {/* FAQ */}
              <motion.div
                className="glass-panel p-8 rounded-xl border border-surface-variant/50"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2 }}
              >
                <h2 className="font-h2 text-h2 text-on-surface mb-6">Quick answers</h2>
                <div className="space-y-3">
                  {faqs.map((faq, i) => (
                    <details key={i} className="group layer-1 rounded-lg">
                      <summary className="p-4 flex items-center justify-between cursor-pointer list-none font-body-md text-body-md text-on-surface">
                        {faq.q}
                        <span className="material-symbols-outlined text-on-surface-variant group-open:rotate-180 transition-transform">expand_more</span>
                      </summary>
                      <div className="px-4 pb-4 text-on-surface-variant font-body-md text-body-md border-t border-outline-variant">
                        {faq.a}
                      </div>
                    </details>
                  ))}
                </div>
              </motion.div>
            </motion.div>
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
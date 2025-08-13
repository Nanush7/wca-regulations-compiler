import re
from wrc.sema.ast import Ruleset
from wrc.codegen.cg import CGDocument

H2 = '\n## {title}\n'
H3 = '\n### {title}\n'
TITLE = '# <wca-title>{title}\n'
VERSION = '<version>{version}'

def special_links_replace(text, urls):
    """
    Replace simplified Regulations and Guidelines links into actual links.
    'urls' dictionary is expected to provide actual links to the targeted
    Regulations and Guidelines, as well as to the PDF file.
    """
    match_number = r'([A-Za-z0-9]+)' + r'(\+*)'
    reference_list = [(r'regulations:article:' + match_number, urls['regulations']),
                      (r'regulations:regulation:' + match_number, urls['regulations']),
                      (r'guidelines:article:' + match_number, urls['guidelines']),
                      (r'guidelines:guideline:' + match_number, urls['guidelines']),
                     ]
    anchor_list = [(r'regulations:contents', urls['regulations'] + r'#contents'),
                   (r'guidelines:contents', urls['guidelines'] + r'#contents'),
                   (r'regulations:top', urls['regulations'] + r'#'),
                   (r'guidelines:top', urls['guidelines'] + r'#'),
                   (r'link:pdf', urls['pdf'] + '.pdf'),
                  ]
    retval = text
    for match, repl in reference_list:
        retval = re.sub(match, repl + r'#\1\2', retval)
    for match, repl in anchor_list:
        retval = re.sub(match, repl, retval)
    return retval

def list2html(text):
    """
    Very simple replacement for lists, no nesting, not even two lists in the
    same 'text'... (yet sufficient for the current regulations)
    Assumes list is in a paragraph.
    """
    match = r'- (.+)\n'
    replace = r'<li>\1</li>\n'
    text = re.sub(match, replace, text)
    # Set start of list
    text = text.replace('<li>', '</p><ul><li>', 1)
    # Set end of list
    tmp = text.rsplit('</li>', 1)
    return '</li></ul><p>'.join(tmp)

def link2html(text):
    """ Turns md links to html """
    match = r'\[([^\]]+)\]\(([^)]+)\)'
    replace = r'<a href="\2">\1</a>'
    return re.sub(match, replace, text)

def simple_md2html(text, urls):
    """ Convert a text from md to html """
    retval = special_links_replace(text, urls)
    # Create a par break for double newlines
    retval = re.sub(r'\n\n', r'</p><p>', retval)
    # Create a visual br for every new line
    retval = re.sub(r'\n', r'<br />\n', retval)
    # Do we really need this ? Help reduce the diff to only '\n' diff.
    retval = re.sub(r'"', r'&quot;', retval)
    retval = list2html(retval)
    return link2html(retval)


class WCADocumentMarkdown(CGDocument):
    name = "Markdown"

    def __init__(self, versionhash, language, pdf):
        super(WCADocumentMarkdown, self).__init__(str)
        self.regset = set()
        self.urls = {'regulations': './', 'guidelines': './', 'pdf': pdf}
        self.language = language
        self.harticle = "\n\n## <article-{num}><{new}><{old}> {name}{sep}{title}\n\n"
        self.guideline = "- {i}) [{label}] {text}\n"
        self.regulation = "- {i}) {text}\n"
        self.label = "- <label>[{name}] {text}\n"
        self.postreg = '\n'
        self.extra_indent = 0

    def visitWCADocument(self, document):
        self.codegen += TITLE.format(title=document.title) + "\n"
        self.codegen += VERSION.format(version=document.version) + "\n\n"

        retval = [self.visit(s) for s in document.sections]

        return retval.count(False) == 0

    def visitlist(self, o):
        return super(WCADocumentMarkdown, self).visitlist(o)

    def visitstr(self, u):
        self.codegen += u
        return True

    def visitTableOfContent(self, toc):
        self.codegen += f"\n\n## {toc.title}\n\n{toc.intro}\n<table-of-contents>\n"
        return True

    def visitSection(self, section):
        self.codegen += H2.format(title=section.title)
        return super(WCADocumentMarkdown, self).visitSection(section)

    def visitArticle(self, article):
        if len(article.number) > 1:
            self.extra_indent = 1
        else:
            self.extra_indent = 0

        self.codegen += self.harticle.format(num=article.number,
                                             old=article.oldtag,
                                             new=article.newtag,
                                             name=article.name,
                                             title=article.title,
                                             sep=article.sep)
        retval = super(WCADocumentMarkdown, self).visit(article.intro)
        retval = retval and super(WCADocumentMarkdown, self).visit(article.content)
        return retval

    def visitSubsection(self, subsection):
        if self.shouldEmitSubsection(self.language, subsection.title):
            self.codegen += H3.format(title=subsection.title)
            return super(WCADocumentMarkdown, self).visitSubsection(subsection)
        return True

    def visitRegulation(self, reg):
        # if reg.
        extra_indent = 0
        self.codegen += "    " * max(0, len(reg.number) - 2 - self.extra_indent)
        self.codegen += self.regulation.format(i=reg.number,
                                               text=reg.text)
        retval = super(WCADocumentMarkdown, self).visitRegulation(reg)
        return retval

    def visitLabelDecl(self, decl):
        self.codegen += self.label.format(name=decl.name, text=decl.text)
        return True

    def visitGuideline(self, guide):
        self.codegen += "    " * max(0, len(guide.number.split("+", 1)[0]) - 2 - self.extra_indent)
        self.codegen += self.guideline.format(i=guide.number,
                                              text=guide.text,
                                              label=guide.labelname)
        return super(WCADocumentMarkdown, self).visitGuideline(guide)

    def emit(self, ast_reg, ast_guide):
        self.regset = Ruleset().get(ast_reg)
        return super(WCADocumentMarkdown, self).emit(ast_reg, ast_guide)

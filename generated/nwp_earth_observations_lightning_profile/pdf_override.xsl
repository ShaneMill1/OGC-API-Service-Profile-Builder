<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:fo="http://www.w3.org/1999/XSL/Format"
                xmlns:mn="https://www.metanorma.org/ns/standoc"
                xmlns:fox="http://xmlgraphics.apache.org/fop/extensions"
                xmlns:xalan="http://xml.apache.org/xalan"
                xmlns:java="http://xml.apache.org/xalan/java"
                xmlns:mnx="https://www.metanorma.org/ns/xslt"
                version="1.0">

  <!-- Suppress the OGC flavor logo on cover/preface (rebranding). -->
  <xsl:template name="insertLogoPreface"/>
  <xsl:template name="insertLogo"/>

  <!-- Remove the 'crossing lines' design element by making it invisible. -->
  <xsl:template name="insertCrossingLines">
    <fo:block-container absolute-position="fixed" width="0mm" height="0mm" font-size="0">
      <fo:block/>
    </fo:block-container>
  </xsl:template>

  <!-- Remove the horizontal rule drawn beneath section titles. -->
  <xsl:template name="insertShortHorizontalLine">
    <fo:block/>
  </xsl:template>
  <xsl:template name="insertBigHorizontalLine">
    <fo:block/>
  </xsl:template>

  <!-- Section-divider number as plain text (no OGC circle), coloured #1F3864. -->
  <xsl:template name="insertSectionNumInCircle">
    <xsl:variable name="sectionNum_"><xsl:call-template name="getSection"/></xsl:variable>
    <xsl:variable name="sectionNum">
      <xsl:choose>
        <xsl:when test="normalize-space($sectionNum_) = '' and self::mn:annex">
          <xsl:number format="A" count="mn:annex[not(@continue = 'true')]" level="any" lang="en"/>
        </xsl:when>
        <xsl:otherwise><xsl:value-of select="$sectionNum_"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <fo:block font-size="24pt" font-weight="bold" color="#1F3864"><xsl:value-of select="$sectionNum"/></fo:block>
  </xsl:template>

  <!-- Suppress section-divider pages by rendering only the main content flow. -->
  <xsl:template match="node()" mode="sections">
    <xsl:param name="num"/>
    <xsl:param name="initial-page-number"/>
    <fo:page-sequence xsl:use-attribute-sets="page-sequence-main">
      <xsl:call-template name="refine_page-sequence-main"/>
      <xsl:call-template name="insertFootnoteSeparator"/>
      <xsl:call-template name="insertHeaderFooter">
        <xsl:with-param name="num" select="$num"/>
      </xsl:call-template>
      <fo:flow flow-name="xsl-region-body">
        <fo:block line-height="125%">
          <xsl:choose>
            <xsl:when test=".//mn:indexsect">
              <xsl:apply-templates select=".//mn:indexsect" mode="index"/>
            </xsl:when>
            <xsl:otherwise>
              <xsl:apply-templates/>
            </xsl:otherwise>
          </xsl:choose>
        </fo:block>
      </fo:flow>
    </fo:page-sequence>
  </xsl:template>

  <!-- Inline Level 1 section titles (e.g. '1. Scope' in a single block, no circles, no table). -->
  <xsl:template match="mn:fmt-title" name="title">
    <xsl:variable name="level"><xsl:call-template name="getLevel"/></xsl:variable>
    <xsl:variable name="element-name">
      <xsl:choose>
        <xsl:when test="../@inline-header = 'true'">fo:inline</xsl:when>
        <xsl:otherwise>fo:block</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:call-template name="setNamedDestination"/>
    <xsl:variable name="title_styles">
      <styles xsl:use-attribute-sets="title-style">
        <xsl:call-template name="refine_title-style"/>
      </styles>
    </xsl:variable>

    <xsl:choose>
      <xsl:when test="$level = 1">
        <fo:block>
          <xsl:copy-of select="xalan:nodeset($title_styles)/styles/@*[local-name() = 'space-before' or local-name() = 'margin-bottom' or local-name() = 'keep-with-next' or local-name() = 'role']"/>
          <xsl:call-template name="setIDforNamedDestinationInline"/>
          <xsl:variable name="title">
            <xsl:choose>
              <xsl:when test="mn:tab">
                <xsl:copy-of select="mn:tab[1]/following-sibling::node()"/>
              </xsl:when>
              <xsl:otherwise><xsl:copy-of select="."/></xsl:otherwise>
            </xsl:choose>
          </xsl:variable>
          <xsl:variable name="section" select="mn:tab[1]/preceding-sibling::node()"/>
          <xsl:call-template name="insertSectionTitle">
            <xsl:with-param name="section" select="$section"/>
            <xsl:with-param name="title" select="$title"/>
            <xsl:with-param name="level" select="$level"/>
          </xsl:call-template>
        </fo:block>
      </xsl:when>
      <xsl:when test="$level = 2">
        <fo:block>
          <xsl:copy-of select="xalan:nodeset($title_styles)/styles/@*[local-name() = 'space-before' or local-name() = 'margin-bottom' or local-name() = 'keep-with-next' or local-name() = 'role']"/>
          <xsl:call-template name="setIDforNamedDestinationInline"/>
          <xsl:variable name="title">
            <xsl:choose>
              <xsl:when test="mn:tab">
                <xsl:copy-of select="mn:tab[1]/following-sibling::node()"/>
              </xsl:when>
              <xsl:otherwise><xsl:copy-of select="."/></xsl:otherwise>
            </xsl:choose>
          </xsl:variable>
          <xsl:variable name="section" select="mn:tab[1]/preceding-sibling::node()"/>
          <xsl:call-template name="insertSectionTitle">
            <xsl:with-param name="section" select="$section"/>
            <xsl:with-param name="title" select="$title"/>
            <xsl:with-param name="level" select="$level"/>
          </xsl:call-template>
        </fo:block>
      </xsl:when>
      <xsl:otherwise>
        <xsl:element name="{$element-name}">
          <xsl:copy-of select="xalan:nodeset($title_styles)/styles/@*"/>
          <xsl:call-template name="setIDforNamedDestinationInline"/>
          <xsl:apply-templates/>
          <xsl:apply-templates select="following-sibling::*[1][self::mn:variant-title][@type = 'sub']" mode="subtitle"/>
        </xsl:element>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Remove the hanging indent on Normative References: the OGC flavor uses
       start-indent 25mm / text-indent -25mm so continuation lines (the title)
       sit indented under the authors. Flatten both to 0 so every line aligns at
       the left margin. -->
  <xsl:attribute-set name="bibitem-normative-style">
    <xsl:attribute name="margin-bottom">12pt</xsl:attribute>
    <xsl:attribute name="start-indent">0mm</xsl:attribute>
    <xsl:attribute name="text-indent">0mm</xsl:attribute>
    <xsl:attribute name="line-height">115%</xsl:attribute>
  </xsl:attribute-set>

  <!-- Same for the non-normative Bibliography section: render the citation tag
       inline with the title as one flush block (wrapped lines align at the left
       margin instead of being indented under the authors). -->
  <xsl:template match="mn:references[not(@normative='true')]/mn:bibitem" name="bibitem_non_normative" priority="2">
    <xsl:param name="skip"/>
    <xsl:call-template name="setNamedDestination"/>
    <fo:block id="{@id}" margin-bottom="12pt" role="SKIP">
      <fo:inline role="SKIP">
        <xsl:apply-templates select="mn:biblio-tag">
          <xsl:with-param name="biblio_tag_part">first</xsl:with-param>
        </xsl:apply-templates>
      </fo:inline>
      <xsl:text> </xsl:text>
      <xsl:call-template name="processBibitem">
        <xsl:with-param name="biblio_tag_part">last</xsl:with-param>
      </xsl:call-template>
    </fo:block>
  </xsl:template>

  <!-- Rebrand the flavor's auto-generated 'Submitting Organizations' sentence
       (the OGC flavor injects 'the Open Geospatial Consortium (OGC)' at its
       presentation stage). Match the clause's paragraph element specifically —
       more specific than the base mn:p template, so mn2pdf's merge appends this
       and it wins for that paragraph only, leaving all other paragraphs alone. -->
  <xsl:template match="mn:clause[@type='submitting_orgs']/mn:p">
    <fo:block xsl:use-attribute-sets="p-style" role="P">The following organizations submitted this Document to DGIWG:</fo:block>
  </xsl:template>

  <!-- Section-divider title colour (readable on a rebranded light page). -->
  <xsl:template name="insertSectionTitleBig">
    <xsl:param name="title"/>
    <fo:block font-size="33pt" margin-bottom="6pt" color="#1F3864">
      <xsl:apply-templates select="xalan:nodeset($title)" mode="titlebig"/>
    </fo:block>
    <xsl:call-template name="insertBigHorizontalLine"/>
  </xsl:template>

  <!-- Every-page diagonal watermark, prepended to the footer region (painted
       over the body, so it also overlays tables). Reproduces the OGC footer. -->
  <xsl:template name="insertFooter">
    <xsl:param name="num"/>
    <xsl:param name="color"/>
    <fo:static-content flow-name="footer" role="artifact">

      <fo:block-container absolute-position="fixed" left="0mm" top="0mm" font-size="0">
        <fo:block>
          <fo:instream-foreign-object content-height="{$pageHeight}mm" content-width="{$pageWidth}mm" fox:alt-text="Watermark">
            <svg xmlns="http://www.w3.org/2000/svg" width="{$pageWidth}mm" height="{$pageHeight}mm" viewBox="0 0 210 297">
              <text x="105" y="150" text-anchor="middle" transform="rotate(-45 105 150)" font-size="38" font-family="Lato" fill="rgb(200,200,200)" fill-opacity="0.55">DRAFT</text>
            </svg>
          </fo:instream-foreign-object>
        </fo:block>
      </fo:block-container>
      <fo:block-container font-size="8pt" color="{$color}" padding-top="6mm">
        <xsl:if test="normalize-space($color) = ''">
          <xsl:variable name="color_text_title">
            <xsl:call-template name="getVariable"><xsl:with-param name="variable">color_text_title</xsl:with-param></xsl:call-template>
          </xsl:variable>
          <xsl:attribute name="color"><xsl:value-of select="$color_text_title"/></xsl:attribute>
        </xsl:if>
        <fo:table table-layout="fixed" width="100%">
          <fo:table-column column-width="90%"/>
          <fo:table-column column-width="10%"/>
          <fo:table-body>
            <fo:table-row>
              <fo:table-cell>
                <fo:block>
                  <fo:inline font-weight="bold">
                    <xsl:call-template name="addLetterSpacing">
                      <xsl:with-param name="text" select="concat($variables/mnx:doc[@num = $num]/copyright-owner, ' ')"/>
                      <xsl:with-param name="letter-spacing" select="0.2"/>
                    </xsl:call-template>
                  </fo:inline>
                  <xsl:call-template name="addLetterSpacing">
                    <xsl:with-param name="text" select="$variables/mnx:doc[@num = $num]/docnumber"/>
                    <xsl:with-param name="letter-spacing" select="0.2"/>
                  </xsl:call-template>
                </fo:block>
              </fo:table-cell>
              <fo:table-cell text-align="right">
                <fo:block font-weight="bold">
                  <fo:page-number/>
                </fo:block>
              </fo:table-cell>
            </fo:table-row>
          </fo:table-body>
        </fo:table>
      </fo:block-container>
    </fo:static-content>
  </xsl:template>

  <!-- Override body font family (OGC default is Lato). -->
  <xsl:attribute-set name="root-style">
    <xsl:attribute name="font-family">Source Sans Pro, STIX Two Math, <xsl:value-of select="$font_noto_sans"/></xsl:attribute>
    <xsl:attribute name="font-family-generic">Sans</xsl:attribute>
    <xsl:attribute name="font-size">11pt</xsl:attribute>
  </xsl:attribute-set>
</xsl:stylesheet>

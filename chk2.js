
if(typeof marked==='undefined'){
  // Fallback: basic markdown parser when CDN fails
  window.marked={
    parse:function(s){
      if(!s)return '';
      var h=s
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/```(\w*)\n([\s\S]*?)```/g,'<pre><code>$2</code></pre>')
        .replace(/`([^`]+)`/g,'<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g,'<em>$1</em>')
        .replace(/^### (.+)$/gm,'<h3>$1</h3>')
        .replace(/^## (.+)$/gm,'<h2>$1</h2>')
        .replace(/^# (.+)$/gm,'<h1>$1</h1>')
        .replace(/^- (.+)$/gm,'<li>$1</li>')
        .replace(/(<li>.*<\/li>\n?)+/g,function(m){return '<ul>'+m+'</ul>'})
        .replace(/\n\n/g,'</p><p>')
        .replace(/\n/g,'<br>');
      return '<div class="md-content">'+h+'</div>';
    }
  };
}

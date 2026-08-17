const Footer = () => {
  return (
    <div className="footer-container">
      <div className="footer-controls">    
        <span className="footer-signature">
          Created by
          <br className="mobile-only" />
          <span className="hide-on-mobile__inline">&nbsp;</span>
          Patrick Petrushonis 
        </span>  
        <ul className="social-icon__container">
          <li className="social-icon">
            <a 
              className="social-linkedin" 
              target="_blank" 
              rel="noopener noreferrer"
              href="https://www.linkedin.com/in/patrick-petrushonis/"
            />
          </li>
          <li className="social-icon">
            <a 
              className="social-github" 
              target="_blank" 
              rel="noopener noreferrer"
              href="https://github.com/PatrickPetrushonis"
            />
          </li>
        </ul>
      </div>
    </div>
  );
};

export default Footer;